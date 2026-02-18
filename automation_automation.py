import subprocess
import sys

def run_batch_simulations():
    # List of all trace files you want to process
    trace_files = [
        "619.lbm_s-2676B.champsimtrace.xz",
        "605.mcf_s-484B.champsimtrace.xz",
        "625.x264_s-12B.champsimtrace.xz",
        "603.bwaves_s-891B.champsimtrace.xz",
        "657.xz_s-56B.champsimtrace.xz",
        "631.deepsjeng_s-928B.champsimtrace.xz",
        "620.omnetpp_s-141B.champsimtrace.xz",
        "641.leela_s-149B.champsimtrace.xz",
        "628.pop2_s-17B.champsimtrace.xz",
        "607.cactuBSSN_s-2421B.champsimtrace.xz",
        "654.roms_s-294B.champsimtrace.xz",
        "649.fotonik3d_s-1B.champsimtrace.xz",
        "648.exchange2_s-72B.champsimtrace.xz",
        "621.wrf_s-575B.champsimtrace.xz",
        "644.nab_s-12459B.champsimtrace.xz"
    ]

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