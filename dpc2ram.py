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
    ap = argparse.ArgumentParser(
        description="Convert DPC3 .xz trace to Ramulator2 SimpleO3Trace format with optional chunking"
    )
    ap.add_argument("input_xz", help="Input DPC trace (.xz)")
    ap.add_argument("--max-chunks", type=int, default=50,
                    help="Maximum number of chunks to generate (0 = unlimited)")
    ap.add_argument("--out", help="Single output trace file (disables chunking)")
    ap.add_argument("--out-dir", help="Directory for chunked output traces")
    ap.add_argument("--chunk-lines", type=int, default=0, help="Lines per chunk (0 = no chunking)")
    ap.add_argument("--inst-limit", type=int, default=0, help="Max instructions to process (0 = unlimited)")
    ap.add_argument("--line-limit", type=int, default=0, help="Max output lines to write (0 = unlimited)")
    ap.add_argument("--phys-capacity", type=int, default=16 * 1024**3,
                    help="Physical address space in bytes (default 16GiB)")
    ap.add_argument("--shift", type=int, default=0, help="Address left shift (0 if byte addr, 6 if cacheline addr)")
    ap.add_argument("--store-mode", choices=["ignore", "rfo", "paired"], default="rfo",
                    help="How to handle store-only ops: ignore | rfo | paired")
    ap.add_argument("--trace-name", type=str, default="trace", help="Base name for chunk files")
    args = ap.parse_args()

    if not os.path.exists(args.input_xz):
        raise FileNotFoundError(args.input_xz)

    if not args.out and not args.out_dir:
        raise ValueError("Specify either --out or --out-dir")

    # If using chunking, require out-dir
    if args.chunk_lines and not args.out_dir and not args.out:
        raise ValueError("Chunking requires --out-dir")

    if args.out_dir:
        os.makedirs(args.out_dir, exist_ok=True)

    bubble = 0
    insts = 0
    lines = 0
    chunk_id = 1
    lines_in_chunk = 0
    f_out = None
    stop_conversion = False

    def open_new_chunk() -> bool:
        nonlocal f_out, chunk_id, lines_in_chunk

        # Enforce max chunks (0 means unlimited)
        if args.max_chunks and chunk_id > args.max_chunks:
            return False

        if f_out:
            f_out.close()

        path = os.path.join(args.out_dir, f"{args.trace_name}_chunk_{chunk_id:03d}.trace")
        f_out = open(path, "w", buffering=10 * 1024 * 1024)
        print(f"Opened {path}")
        lines_in_chunk = 0
        chunk_id += 1
        return True

    # Open first output
    if args.out:
        # Single-file mode: ignore chunking
        f_out = open(args.out, "w", buffering=10 * 1024 * 1024)
    else:
        # Chunked mode
        if not open_new_chunk():
            print(f"Stopped after max_chunks={args.max_chunks}")
            return

    with lzma.open(args.input_xz, "rb") as f_in:
        with tqdm(unit="rec", desc="Converting") as pbar:
            while True:
                if stop_conversion:
                    break
                if args.inst_limit and insts >= args.inst_limit:
                    break
                if args.line_limit and lines >= args.line_limit:
                    break

                rec = f_in.read(RECORD_SIZE)
                if not rec or len(rec) < RECORD_SIZE:
                    break

                pbar.update(1)

                ip, is_branch, taken, d_reg, s_reg, d0, d1, s0, s1 = UNPACKER.unpack(rec)
                insts += 1

                loads = [a for a in (s0, s1) if a]
                stores = [a for a in (d0, d1) if a]

                # No memory ops -> just a bubble
                if not loads and not stores:
                    bubble += 1
                    continue

                def emit(load_raw: int, wb_raw: Optional[int]):
                    nonlocal bubble, lines, lines_in_chunk, f_out, stop_conversion

                    if stop_conversion:
                        return

                    # If chunking enabled, roll over to next chunk file
                    if not args.out and args.chunk_lines and lines_in_chunk >= args.chunk_lines:
                        if not open_new_chunk():
                            stop_conversion = True
                            return

                    load_addr = convert_addr(load_raw, args.phys_capacity, args.shift)
                    if wb_raw is None:
                        f_out.write(f"{bubble} {load_addr}\n")
                    else:
                        wb_addr = convert_addr(wb_raw, args.phys_capacity, args.shift)
                        f_out.write(f"{bubble} {load_addr} {wb_addr}\n")

                    bubble = 0
                    lines += 1
                    lines_in_chunk += 1

                    # Respect global line limit as an extra guard
                    if args.line_limit and lines >= args.line_limit:
                        stop_conversion = True

                # Prefer emitting LOADs as the "load_addr"
                if loads:
                    wb = stores[0] if stores else None
                    emit(loads[0], wb)

                    # If a record contains more than one load, emit extra lines with bubble=0
                    for extra in loads[1:]:
                        if stop_conversion:
                            break
                        emit(extra, None)
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

    if f_out:
        f_out.close()

    if args.max_chunks and not args.out and chunk_id > args.max_chunks:
        print(f"Stopped after max_chunks={args.max_chunks}")

    print("\nDone.")
    print(f"Instructions processed: {insts:,}")
    print(f"Lines written:          {lines:,}")
    if args.out:
        print(f"Output:                {args.out}")
    else:
        print(f"Output directory:      {args.out_dir}")

if __name__ == "__main__":
    main()