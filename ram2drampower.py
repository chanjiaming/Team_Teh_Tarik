import sys

def convert_ramulator_to_drampower(input_filename, output_filename):
    with open(input_filename, 'r') as f_in, open(output_filename, 'w') as f_out:
        last_ts = 0
        for line in f_in:
            parts = [p.strip() for p in line.split(',')]
            if len(parts) < 8: continue

            # Ramulator: clk(0), cmd(1), channel(2), rank(3), bg(4), bank(5), row(6), col(7)
            ts, cmd, _, rank, bg, bank, row, col = parts
            
            # 1. Command Mapping
            # Ramulator uses 'REFab', DRAMPower usually expects 'REF'
            if cmd == "REFab": cmd = "REF"
            
            # 2. Handle Placeholders
            # DRAMPower usually prefers '0' over '-1' for non-addressed commands
            rank = '0' if rank == '-1' else rank
            bg   = '0' if bg == '-1' else bg
            bank = '0' if bank == '-1' else bank
            row  = '0' if row == '-1' else row
            col  = '0' if col == '-1' else col

            # 3. Construct DRAMPower Columns
            # Format: timestamp, command, rank, bank_group, bank, row, column, [data]
            out_row = [ts, cmd, rank, bg, bank, row, col]
            
            # 4. Add dummy data for Read/Write commands (required by some DRAMPower versions)
            if cmd in ["RD", "WR"]:
                out_row.append("0000000000000000") 

            f_out.write(",".join(out_row) + "\n")
            last_ts = ts

        # 5. Add END command to signify end of trace
        f_out.write(f"{int(last_ts) + 1},END,0,0,0,0,0\n")

if __name__ == "__main__":
    if len(sys.argv) == 3:
        convert_ramulator_to_drampower(sys.argv[1], sys.argv[2]) 
    else:
        print("Usage: python3 ram2drampower.py <input_file_name.txt.ch0> <output_file.csv>")