import os
import yaml
import subprocess
import glob
# --- SETTINGS ---
DO_CONVERSION = True 
DO_RAMU2_SIM = True
DO_DRAMPOWER_CONV = True 
DO_DRAMPOWER_CLI = True

# Paths
baseline_config_file = "automation.yaml"
#dpc_file_name = "605.mcf_s-484B.champsimtrace.xz"
#dpc_file_name = "625.x264_s-12B.champsimtrace.xz"
#dpc_file_name = "603.bwaves_s-891B.champsimtrace.xz"
#dpc_file_name = "657.xz_s-56B.champsimtrace.xz"
dpc_file_name = "631.deepsjeng_s-928B.champsimtrace.xz"
parts = dpc_file_name.split('.')
trace_name = parts[1]  

# Script & Binary Locations
dpc2ram_script = "/home/eevee/Documents/team_teh_tarik/trace_file/dpc2ram.py"
ram2drampower_script = "/home/eevee/Documents/team_teh_tarik/trace_file/ram2drampower.py"

# DRAMPower Paths
drampower_bin = "/home/eevee/Documents/team_teh_tarik/drampower/DRAMPower/build/bin/cli"
dram_spec_json = "/home/eevee/Documents/team_teh_tarik/drampower/DRAMPower/tests/tests_drampower/resources/ddr5.json"
cli_config_json = "/home/eevee/Documents/team_teh_tarik/drampower/DRAMPower/tests/tests_drampower/resources/cliconfig.json"

# Data Paths
input_xz_trace = "/home/eevee/Downloads/" + dpc_file_name 
ramulator_trace_input = "/home/eevee/Documents/team_teh_tarik/trace_file/ramulator_tf/" + trace_name + ".trace"
chunk_dir = "/home/eevee/Documents/team_teh_tarik/trace_file/ramulator_tf/" + trace_name + "_chunks"

tREFI_list = [3900, 7800, 11700]
interval_list = [64, 128, 192]

# --- Step 1: Converting DPC2 trace ---
if DO_CONVERSION:
    print("--- Step 1: Converting DPC trace ---")
    try:
        subprocess.run([
            "python3",
            dpc2ram_script,
            input_xz_trace,
            "--out-dir", chunk_dir,
            "--trace-name", trace_name,
            "--chunk-lines", "200000",
            "--inst-limit", "0",
            "--line-limit", "0",
            "--shift", "0",
            "--store-mode", "paired"
        ], check=True)
    except Exception as e:
        print(f"Step 1 failed: {e}")
        exit(1)

    chunk_files = sorted(glob.glob(f"{chunk_dir}/{trace_name}_chunk_*.trace"))
    #home/eevee/Documents/team_teh_tarik/trace_file/ramulator_tf/x264_s-12B_chunks/chunk_030.trace
    #chunk_dir = "/home/eevee/Documents/team_teh_tarik/trace_file/ramulator_tf/" + trace_name + "_chunks"
    if not chunk_files:
        print("No chunk files generated!")
        exit(1)

#python3 dpc2ram.py 625.x264.xz --out x264.simple.trace --inst-limit 200000 --line-limit 200000 --shift 6 --store-mode paired"""

# 2. Load the baseline config
with open(baseline_config_file, 'r') as f:
    base_config = yaml.safe_load(f)

# 3. Main Loop
for chunk_trace in chunk_files:
    chunk_tag = os.path.splitext(os.path.basename(chunk_trace))[0]
    for tREFI, interval in zip(tREFI_list, interval_list):
        base_config["MemorySystem"]["DRAM"]["timing"]["tREFI"] = tREFI
        
        output_base = f"/home/eevee/Documents/team_teh_tarik/result/{trace_name}/{trace_name}_{chunk_tag}/{chunk_tag}_{trace_name}_{interval}ms"
        if not os.path.exists(output_base):
            os.makedirs(output_base)
        ramulator_trace_output = output_base + f"/{trace_name}_{interval}ms_ramulator2_output.txt"
        drampower_trace_input = output_base + f"/{trace_name}_{interval}ms_drampower_trace_input.csv"
        drampower_report_output = output_base + f"/{trace_name}_{interval}ms_drampower_report.txt"

        # Update Path in Plugins

        for plugin in base_config["MemorySystem"]["Controller"]["plugins"]:
            if "ControllerPlugin" in plugin:
                plugin["ControllerPlugin"]["path"] = ramulator_trace_output

        base_config["Frontend"]["traces"] = [chunk_trace]

        temp_config_name = f"temp_config_{interval}ms.yaml"
        with open(temp_config_name, 'w') as f:
            yaml.dump(base_config, f)

        # --- Step 2: Running Simulation ---
        if DO_RAMU2_SIM:
            print(f"\n--- Step 2: Running Simulation ({interval}ms) ---")
            print(f"Fetching trace file: {ramulator_trace_input}")
            try:
                with open(output_base + f"/{trace_name}_{interval}ms_ramulator2_report.txt", "w") as output_file:
                    subprocess.run(["./build/ramulator2", "-f", temp_config_name], check=True, stdout=output_file, stderr=output_file)
            except Exception as e:
                print(f"Step 2 failed: {e}")
                continue

        # --- Step 3: Convert to DRAMPower ---
        if DO_DRAMPOWER_CONV:
            print(f"\n--- Step 3: Converting to DRAMPower format ---")
            print(f"Converting trace file: {ramulator_trace_output}.ch0")
            try:
                if os.path.exists(ramulator_trace_output + ".ch0"):
                    env = os.environ.copy()
                    env["PYTHONPATH"] = "/home/eevee/Documents/team_teh_tarik/trace_file/:" + env.get("PYTHONPATH", "")
                    
                    subprocess.run(
                        ["python3", ram2drampower_script, ramulator_trace_output + ".ch0", drampower_trace_input], 
                        check=True, env=env
                    )
                    print(f"DRAMPower trace saved: {drampower_trace_input}")
                else:
                    print(f"Error: {ramulator_trace_output} not found.")
            except Exception as e:
                print(f"Step 3 failed: {e}")

        # --- Step 4: Run DRAMPower CLI ---
        if DO_DRAMPOWER_CLI:
            print(f"\n--- Step 4: Calculating Energy with DRAMPower ---")
            try:
                result = subprocess.run([
                    drampower_bin, "-m", dram_spec_json, "-t", drampower_trace_input, "-c", cli_config_json
                ], capture_output=True, text=True, check=True)
                

                with open(drampower_report_output, "w") as f_report:
                    f_report.write(result.stdout)
                print(f"Report saved: {drampower_report_output}")
            except Exception as e:
                print(f"Step 4 failed: {e}")

        if os.path.exists(temp_config_name):
            os.remove(temp_config_name)

print("\nAll tasks complete!")