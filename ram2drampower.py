import sys
import argparse


def convert_ramulator_to_drampower(input_filename, output_filename, rank_num=2, trfc=710):
    refresh_end_time = 0
    last_ts = 0

    with open(input_filename, 'r') as f_in, open(output_filename, 'w') as f_out:

        for line in f_in:
            parts = [p.strip() for p in line.split(',')]
            if len(parts) < 8:
                continue

            ts_str, cmd, _, rank, bg, bank, row, col = parts
            ts = int(ts_str)

            # ---- Enforce refresh blocking ----
            if ts < refresh_end_time:
                ts = refresh_end_time

            propagate_refresh = False

            # ---- Command Mapping ----
            if cmd in ["REFab", "REF"]:
                cmd = "REFA"
                propagate_refresh = True
            elif cmd == "REFpb":
                cmd = "REFB"
            elif cmd == "REFsb":
                cmd = "REFSB"

            # ---- Replace -1 placeholders ----
            rank = '0' if rank == '-1' else rank
            bg   = '0' if bg == '-1' else bg
            bank = '0' if bank == '-1' else bank
            row  = '0' if row == '-1' else row
            col  = '0' if col == '-1' else col

            # ---- Handle Refresh ----
            if cmd == "REFA":
                refresh_end_time = ts + trfc

                for r in range(rank_num):
                    out_row = [str(ts), cmd, str(r), '0', '0', '0', '0']
                    f_out.write(",".join(out_row) + "\n")

            else:
                out_row = [str(ts), cmd, rank, bg, bank, row, col]

                if cmd in ["RD", "WR"]:
                    out_row.append("0000000000000000")

                f_out.write(",".join(out_row) + "\n")

            last_ts = ts

        # ---- Add END with sufficient slack ----
        end_time = last_ts + trfc + 100
        f_out.write(f"{end_time},END,0,0,0,0,0\n")

    print(f"Conversion complete. Last timestamp: {last_ts}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("input", help="Ramulator2 trace input")
    parser.add_argument("output", help="DRAMPower CSV output")
    parser.add_argument("--rank_num", type=int, default=2, help="Number of ranks (default=2)")
    parser.add_argument("--trfc", type=int, default=710, help="tRFC cycles (default=710)")

    args = parser.parse_args()

    convert_ramulator_to_drampower(
        args.input,
        args.output,
        rank_num=args.rank_num,
        trfc=args.trfc
    )