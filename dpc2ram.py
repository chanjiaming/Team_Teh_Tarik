import lzma
import struct
import sys
import os

# Check if tqdm is installed for the progress bar
try:
    from tqdm import tqdm
except ImportError:
    print("tqdm not found. Install it using: pip install tqdm")
    # Simple fallback if tqdm isn't available
    def tqdm(iterable, **kwargs):
        return iterable

# --- CONFIGURATION ---
# 16 GB = 16 * 1024 * 1024 * 1024 bytes
PHYSICAL_CAPACITY = 17179869184 


# DPC3/SPEC17 Binary Structure (64 bytes per instruction)
# Format: IP(8), branch(1), taken(1), d_reg(3), s_reg(3), d_mem(16), s_mem(16), pad(16)
STRUCT_FMT = "<Q B B 3s 3s 2Q 2Q 16x"
STRUCT_SIZE = 64
unpacker = struct.Struct(STRUCT_FMT)

def convert_trace(input_xz, output_trace, request_limit = 15000000):
    REQUEST_LIMIT = int(request_limit)
    if not os.path.exists(input_xz):
        print(f"Error: File {input_xz} not found.")
        return

    file_size = os.path.getsize(input_xz)
    print(f"Opening binary trace: {input_xz}")
    print(f"Targeting {REQUEST_LIMIT:,} requests for approximately 100ms of simulation.")

    count = 0
    # Use a 10MB buffer for faster writing to disk
    with lzma.open(input_xz, "rb") as f_in, \
         open(output_trace, "w", buffering=10*1024*1024) as f_out:
        
        with tqdm(total=file_size, unit='B', unit_scale=True, desc="Converting") as pbar:
            last_pos = 0
            while count < REQUEST_LIMIT:
                chunk = f_in.read(STRUCT_SIZE)
                if not chunk:
                    break
                
                # Update progress bar based on compressed file position
                current_pos = f_in.tell()
                pbar.update(current_pos - last_pos)
                last_pos = current_pos

                if len(chunk) < STRUCT_SIZE:
                    break
                
                data = unpacker.unpack(chunk)
                
                # Indices 7,8 are Source Memory Addresses (Reads)
                for addr in data[7:9]:
                    if addr != 0:
                        f_out.write(f"R {addr % PHYSICAL_CAPACITY}\n")
                        count += 1
                        if count >= REQUEST_LIMIT: break
                
                # Indices 5,6 are Destination Memory Addresses (Writes)
                if count < REQUEST_LIMIT:
                    for addr in data[5:7]:
                        if addr != 0:
                            f_out.write(f"W {addr % PHYSICAL_CAPACITY}\n")
                            count += 1
                            if count >= REQUEST_LIMIT: break

if __name__ == "__main__":
    if len(sys.argv) == 3:
        convert_trace(sys.argv[1], sys.argv[2])  # Use default REQUEST_LIMIT
    elif len(sys.argv) == 4:
        convert_trace(sys.argv[1], sys.argv[2], sys.argv[3])  # Use provided REQUEST_LIMIT
    else:
        print("Usage: python3 dpc2ram.py <input_file.xz> <output_file.trace> [request_limit]")



