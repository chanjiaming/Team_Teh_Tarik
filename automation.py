import os
import yaml
import subprocess

# --- SETTINGS ---
DO_CONVERSION = True 
DO_RAMU2_SIM = True
DO_DRAMPOWER_CONV = True 
DO_DRAMPOWER_CLI = True

# Paths
baseline_config_file = "automation.yaml"
dpc_file_name = "605.mcf_s-484B.champsimtrace.xz"
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
output_converted_trace = "/home/eevee/Documents/team_teh_tarik/trace_file/ramulator_tf/" + trace_name + ".trace"

tREFI_list = [3900, 7800, 11700]
interval_list = [64, 128, 192]

# --- Step 1: Converting DPC2 trace ---
if DO_CONVERSION:
    print(f"--- Step 1: Converting DPC2 trace ---")
    try:
        subprocess.run(["python3", dpc2ram_script, input_xz_trace, output_converted_trace], check=True)
    except Exception as e:
        print(f"Step 1 failed: {e}")
        exit(1)

# 2. Load the baseline config
with open(baseline_config_file, 'r') as f:
    base_config = yaml.safe_load(f)

# 3. Main Loop
for tREFI, interval in zip(tREFI_list, interval_list):
    base_config["MemorySystem"]["DRAM"]["timing"]["tREFI"] = tREFI
    
    sim_output_base = f"/home/eevee/Documents/team_teh_tarik/ramulator2/{trace_name}_ramulator_trace_{interval}_ms.txt"
    actual_sim_output = sim_output_base + ".ch0"
    drampower_output = sim_output_base.replace(".txt", "_drampower.csv")

    # Update Path in Plugins
    for plugin in base_config["MemorySystem"]["Controller"]["plugins"]:
        if "ControllerPlugin" in plugin:
            plugin["ControllerPlugin"]["path"] = sim_output_base
    
    base_config["Frontend"]["path"] = output_converted_trace

    temp_config_name = f"temp_config_{interval}ms.yaml"
    with open(temp_config_name, 'w') as f:
        yaml.dump(base_config, f)

    # --- Step 2: Running Simulation ---
    if DO_RAMU2_SIM:
        print(f"--- Step 2: Running Simulation ({interval}ms) ---")
        try:
            subprocess.run(["./build/ramulator2", "-f", temp_config_name], check=True)
        except Exception as e:
            print(f"Step 2 failed: {e}")
            continue

    # --- Step 3: Convert to DRAMPower ---
    if DO_DRAMPOWER_CONV:
        print(f"--- Step 3: Converting to DRAMPower format ---")
        try:
            if os.path.exists(actual_sim_output):
                # Fixing the "No module named" error by adding the directory to PYTHONPATH
                env = os.environ.copy()
                env["PYTHONPATH"] = "/home/eevee/Documents/team_teh_tarik/trace_file/:" + env.get("PYTHONPATH", "")
                
                subprocess.run(
                    ["python3", ram2drampower_script, actual_sim_output, drampower_output], 
                    check=True, env=env
                )
                print(f"DRAMPower trace saved: {drampower_output}")
            else:
                print(f"Error: {actual_sim_output} not found.")
        except Exception as e:
            print(f"Step 3 failed: {e}")

    # --- Step 4: Run DRAMPower CLI ---
    if DO_DRAMPOWER_CLI:
        print(f"--- Step 4: Calculating Energy with DRAMPower ---")
        try:
            result = subprocess.run([
                drampower_bin, "-m", dram_spec_json, "-t", drampower_output, "-c", cli_config_json
            ], capture_output=True, text=True, check=True)
            
            report_name = sim_output_base.replace(".txt", "_energy_report.txt")
            with open(report_name, "w") as f_report:
                f_report.write(result.stdout)
            print(f"Report saved: {report_name}")
        except Exception as e:
            print(f"Step 4 failed: {e}")

    if os.path.exists(temp_config_name):
        os.remove(temp_config_name)

print("\nAll tasks complete!")