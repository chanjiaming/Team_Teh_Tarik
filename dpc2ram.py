#!/usr/bin/env python3
import argparse
import lzma
import os
import struct
from tqdm import tqdm
from typing import Optional

# DPC3 record: 64 bytes
STRUCT_FMT = "<Q B B 3s 3s 2Q 2Q 16x"
RECORD_SIZE = 64
UNPACKER = struct.Struct(STRUCT_FMT)

def mask_addr(addr: int, phys_capacity: int) -> int:
    # keep entropy if power-of-two
    if (phys_capacity & (phys_capacity - 1)) == 0:
        return addr & (phys_capacity - 1)
    return addr % phys_capacity

def convert_addr(raw: int, phys_capacity: int, shift: int) -> int:
    # shift=6 if raw is cacheline address; shift=0 if raw is already byte address
    return mask_addr(raw << shift, phys_capacity)

def main():
    ap = argparse.ArgumentParser(description="Convert DPC3 .xz trace to Ramulator2 SimpleO3Trace format: <bubble_count> <load_addr> [writeback_addr]")
    ap.add_argument("input_xz", help="Input DPC trace (.xz)")
    ap.add_argument("--out", required=True, help="Output trace file for SimpleO3")
    ap.add_argument("--inst-limit", type=int, default=0, help="Max instructions to process (0 = unlimited)")
    ap.add_argument("--line-limit", type=int, default=0, help="Max output lines to write (0 = unlimited)")
    ap.add_argument("--phys-capacity", type=int, default=16 * 1024**3, help="Physical address space in bytes (default 16GiB)")
    ap.add_argument("--shift", type=int, default=0, help="Address left shift (0 if byte addr, 6 if cacheline addr)")
    ap.add_argument("--store-mode", choices=["ignore", "rfo", "paired"], default="rfo",
                    help="How to handle store-only ops: ignore | rfo | paired")
    args = ap.parse_args()

    if not os.path.exists(args.input_xz):
        raise FileNotFoundError(args.input_xz)

    compressed_size = os.path.getsize(args.input_xz)

    bubble = 0
    insts = 0
    lines = 0

    with lzma.open(args.input_xz, "rb") as f_in, open(args.out, "w", buffering=10*1024*1024) as f_out:
        with tqdm(total=compressed_size, unit="B", unit_scale=True, desc="Converting") as pbar:
            last_pos = 0

            while True:
                if args.inst_limit and insts >= args.inst_limit:
                    break
                if args.line_limit and lines >= args.line_limit:
                    break

                chunk = f_in.read(RECORD_SIZE)
                if not chunk or len(chunk) < RECORD_SIZE:
                    break

                # progress by compressed bytes consumed
                cur = f_in.tell()
                pbar.update(cur - last_pos)
                last_pos = cur

                ip, is_branch, taken, d_reg, s_reg, d0, d1, s0, s1 = UNPACKER.unpack(chunk)
                insts += 1

                loads = [a for a in (s0, s1) if a]
                stores = [a for a in (d0, d1) if a]

                # No memory ops -> just a bubble
                if not loads and not stores:
                    bubble += 1
                    continue

                def emit(load_raw: int, wb_raw: Optional[int]):
                    nonlocal bubble, lines
                    load_addr = convert_addr(load_raw, args.phys_capacity, args.shift)
                    if wb_raw is None:
                        f_out.write(f"{bubble} {load_addr}\n")
                    else:
                        wb_addr = convert_addr(wb_raw, args.phys_capacity, args.shift)
                        f_out.write(f"{bubble} {load_addr} {wb_addr}\n")
                    bubble = 0
                    lines += 1

                # Prefer emitting LOADs as the "load_addr"
                if loads:
                    # If there is also a store in this same DPC record, we *optionally* use it
                    # as a writeback approximation for the first emitted load.
                    wb = stores[0] if stores else None
                    emit(loads[0], wb)

                    # If a record contains more than one load, emit extra lines with bubble=0
                    for extra in loads[1:]:
                        if args.line_limit and lines >= args.line_limit:
                            break
                        # Extra loads in same instruction get no bubble
                        saved_bubble = bubble
                        bubble = 0
                        emit(extra, None)
                        bubble = 0

                    continue

                # Store-only instruction
                if stores:
                    if args.store_mode == "ignore":
                        bubble += 1
                        continue
                    elif args.store_mode == "rfo":
                        emit(stores[0], None)  # treat as RFO read
                    else:  # paired
                        emit(stores[0], stores[0])  # read + writeback (approx)

    print("\nDone.")
    print(f"Instructions processed: {insts:,}")
    print(f"Lines written:          {lines:,} -> {args.out}")

if __name__ == "__main__":
    main()


"""
example usage
python3 dpc2ram.py 625.x264.xz --out x264.simple.trace --inst-limit 200000 --line-limit 200000 --shift 6 --store-mode paired"""
