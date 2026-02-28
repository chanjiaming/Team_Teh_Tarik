import subprocess
import sys
import os
import glob

def run_batch_simulations():
    trace_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "trace_files")
    trace_files = [os.path.basename(f) for f in glob.glob(os.path.join(trace_dir, "*.xz"))]
    if not trace_files:
        print(f"No .xz traces found in {trace_dir}!")
        return

    print(f"Starting batch processing of {len(trace_files)} traces...")
    print("-" * 50)

    for i, trace in enumerate(trace_files, 1):
        print(f"[{i}/{len(trace_files)}] Processing: {trace}")
        
        try:
            subprocess.run(["python3", "automation.py", trace], check=True)
            print(f"Successfully finished: {trace}\n")
            
        except subprocess.CalledProcessError as e:
            print(f"!!! Error occurred while processing {trace} !!!")
            print(f"Return code: {e.returncode}")

            continue 

    print("-" * 50)
    print("Batch processing complete!")

if __name__ == "__main__":
    run_batch_simulations()