import sys
import argparse

def convert_ramulator_to_drampower(input_filename, output_filename):
    with open(input_filename, 'r') as f_in, open(output_filename, 'w') as f_out:
        last_ts = 0

        for line in f_in:
            parts = [p.strip() for p in line.split(',')]
            if len(parts) < 8:
                continue

            ts, cmd, _, rank, bg, bank, row, col = parts

            if   cmd == "REFab": cmd = "REFA"
            elif cmd == "REFpb": cmd = "REFB"
            elif cmd == "REFsb": cmd = "REFSB"

            rank = '0' if rank == '-1' else rank
            bg   = '0' if bg == '-1' else bg
            bank = '0' if bank == '-1' else bank
            row  = '0' if row == '-1' else row
            col  = '0' if col == '-1' else col

            out_row = [ts, cmd, rank, bg, bank, row, col]
            if cmd in ["RD", "WR"]:
                out_row.append("0000000000000000")
            f_out.write(",".join(out_row) + "\n")

            last_ts = ts
        f_out.write(f"{int(last_ts)+ 20000},END,0,0,0,0,0\n")
        print(f"Last timestamp: {last_ts}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("input")
    parser.add_argument("output")
    args = parser.parse_args()

    convert_ramulator_to_drampower(args.input, args.output)