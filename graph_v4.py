#!/usr/bin/env python3
import os
import re
import math
import statistics
from collections import defaultdict, Counter
import numpy as np
import pandas as pd
from pathlib import Path
import matplotlib.pyplot as plt


# --- Configuration & Paths ---
BASE_PATH = os.path.expanduser('/home/eevee/Documents/team_teh_tarik/result')
OUT_PATH = "/home/eevee/Documents/team_teh_tarik/graph"
FREQ_MHZ = 2400
CONFIGS = ['32ms', '48ms', '64ms']

# SER model params
FIT_PER_GB = 100         # 100 FIT / GB
DEVICE_Gb = 16 * 20     #20 dies in total, 16 storage + 4
EPS = 1e-30                # protect divide-by-zero
# Using the precise coefficients from your updated math
ratio_retent =  { "32ms": 1.0, "48ms": 2.2628, "64ms": 4.0395 }

# --- Regex Patterns (Performance & AI Features) ---
ENERGY_RE = re.compile(r"Total Energy ->\s*([\d\.eE\-\+]+)")
LAT_RE    = re.compile(r"avg_read_latency_0:\s*([\d\.]+)")
CYC_RE    = re.compile(r"memory_system_cycles:\s*([\d\.]+)")
REFAB_RE  = re.compile(r"\bREFab\b")

# AI Feature Regex (Supports multiple log formats)
READ_RE   = re.compile(r"num_read_reqs_0:\s*([\d\.]+)|number_of_read_requests:\s*([\d\.]+)")
WRITE_RE  = re.compile(r"num_write_reqs_0:\s*([\d\.]+)|number_of_write_requests:\s*([\d\.]+)")
HITS_RE   = re.compile(r"row_hits_0:\s*([\d\.]+)|row_hits:\s*([\d\.]+)")
RMISS_RE  = re.compile(r"row_misses_0:\s*([\d\.]+)|row_misses:\s*([\d\.]+)")
RCONF_RE  = re.compile(r"row_conflicts_0:\s*([\d\.]+)|row_conflicts:\s*([\d\.]+)")
LLC_M_RE  = re.compile(r"llc_read_misses:\s*([\d\.]+)|cache_read_misses:\s*([\d\.]+)")
LLC_A_RE  = re.compile(r"llc_read_access:\s*([\d\.]+)|cache_read_access:\s*([\d\.]+)")

selected_cfg = {
    "bwaves": "48ms",
    "cactuBSSN": "32ms",
    "deepsjeng": "64ms",
    "exchange2": "48ms",
    "fotonik3d": "48ms",
    "lbm": "48ms",
    "leela": "64ms",
    "mcf": "64ms",
    "nab": "64ms",
    "omnetpp": "32ms",
    "pop2": "48ms",
    "roms": "48ms",
    "wrf": "48ms",
    "x264": "32ms",
    "xz": "32ms"
}

def detect_trace_key(name: str) -> str:
    #print(f"Detecting trace key from name: {name}")
    return name.split('_')[0] if '_' in name else name

def safe_float(regex, text, label=""):
    m = regex.search(text)
    if not m: return 0.0
    # Return the first non-None group (handles OR in regex)
    for group in m.groups():
        if group is not None: return float(group)
    return 0.0

# --- 1. Data Collection ---
print(f"Scanning: {BASE_PATH}")
trace_roots = set()
for root, dirs, _ in os.walk(BASE_PATH):
    if any(any(cfg in d for cfg in CONFIGS) for d in dirs):
        trace_roots.add(root)

aggregated = defaultdict(lambda: {cfg: [] for cfg in CONFIGS})

for trace_path in sorted(trace_roots):
    trace_key = detect_trace_key(os.path.basename(trace_path))
    for cfg in CONFIGS:
        cfg_folder = next((d for d in os.listdir(trace_path) if cfg in d), None)
        if not cfg_folder: continue
        
        full_path = os.path.join(trace_path, cfg_folder)
        dp_file  = next((f for f in os.listdir(full_path) if 'drampower_report' in f), None)
        ram_file = next((f for f in os.listdir(full_path) if 'ramulator2_report' in f), None)
        ram_out_file = next((f for f in os.listdir(full_path) if 'ramulator2_output.txt.ch0' in f), None)
        if not dp_file or not ram_file: continue

        try:
            with open(os.path.join(full_path, dp_file), 'r') as f:
                dp_txt = f.read()
                E = safe_float(ENERGY_RE, dp_txt, "Energy")

            with open(os.path.join(full_path, ram_file), 'r') as f:
                ram_txt = f.read()
                lat_cyc = safe_float(LAT_RE, ram_txt)
                tot_cyc = safe_float(CYC_RE, ram_txt)
                # AI Feature extraction
                n_read, n_write = safe_float(READ_RE, ram_txt), safe_float(WRITE_RE, ram_txt)
                r_hit, r_miss, r_conf = safe_float(HITS_RE, ram_txt), safe_float(RMISS_RE, ram_txt), safe_float(RCONF_RE, ram_txt)
                l_miss, l_acc = safe_float(LLC_M_RE, ram_txt), safe_float(LLC_A_RE, ram_txt)
            
            with open(os.path.join(full_path, ram_out_file), 'r') as f:
                refab_count = sum(1 for line in f if 'REFab' in line)
            
            # Performance Math
            freq_hz = FREQ_MHZ * 1e6
            lat_sec = lat_cyc / freq_hz
            duration_hours = (tot_cyc / freq_hz) / 3600.0
            M = E * (lat_sec ** 2)
            
            # Reliability Math
            mu = (FIT_PER_GB / 1e9) * DEVICE_Gb * duration_hours
            SER = 1.0 - math.exp(-mu)

            # AI Calculation
            total_reqs = n_read + n_write
            denom_rb = r_hit + r_miss + r_conf
            
            # Append all metrics to avoid KeyErrors
            aggregated[trace_key][cfg].append({
                "E": E, "lat_sec": lat_sec, "hours": duration_hours, "M": M, "SER": SER,
                "Incoming_Req_Per_Cycle": total_reqs / tot_cyc if tot_cyc > 0 else 0,
                "Read_Intensity": n_read / total_reqs if total_reqs > 0 else 0,
                "RB_Locality": r_hit / denom_rb if denom_rb > 0 else 0,
                "RB_Conflict_Rate": r_conf / denom_rb if denom_rb > 0 else 0,
                "LLC_Miss_Rate": l_miss / l_acc if l_acc > 0 else 0,
                "REFab": refab_count
            })
        except Exception as e:
            continue

# --- 2. Aggregation ---
data = defaultdict(dict)
for trace_key, cfgs in aggregated.items():
    for cfg, runs in cfgs.items():
        if not runs: continue
        data[trace_key][cfg] = {
            "M": statistics.mean(r["M"] for r in runs),
            "SER": statistics.mean(r["SER"] for r in runs),
            "n_runs": len(runs),
            "runs": runs,  # Keep raw runs for export
            "REFab": statistics.mean(r["REFab"] for r in runs),
        }

valid_traces = [t for t in sorted(data.keys()) if all(c in data[t] for c in CONFIGS)]
if not valid_traces: raise SystemExit("No valid traces found.")

# --- 3. Data Processing & Normalization ---
plot_records = []
scatter_records = []
refab_records = []

for t in valid_traces:
    # 1. Establish the 32ms baseline for this specific trace
    # We use the mean of 32ms runs as the 1.0 reference point
    base_e = statistics.mean(r["E"] for r in data[t]["32ms"]["runs"])
    base_lat = statistics.mean(r["lat_sec"] for r in data[t]["32ms"]["runs"])
    base_m = data[t]["32ms"]["M"]
    
    # Store data for the Bar Chart (Averages)
    row = {"trace": t}
    for cfg in CONFIGS:
        row[cfg] = data[t][cfg]["M"] / base_m
        
        
        # Store data for the Scatter Plot (Individual Runs)
        for run in data[t][cfg]["runs"]:
            scatter_records.append({
                "trace": t,
                "cfg": cfg,
                "energy_norm": run["E"] / base_e,
                "lat_norm": run["lat_sec"] / base_lat
            })
    plot_records.append(row)

for t in valid_traces:
    row = {"trace": t}
    for cfg in CONFIGS:
        #row[cfg] = data[t][cfg]["REFab"]
        row[cfg] = data[t][cfg]["REFab"] / data[t]["32ms"]["REFab"]
    refab_records.append(row)


# Convert to DataFrames
df_M = pd.DataFrame(plot_records).set_index("trace")
df_refab = pd.DataFrame(refab_records).set_index("trace")
df_scatter = pd.DataFrame(scatter_records)


# Geometric mean improvement in M vs 32ms baseline
geo_impr_48_M = 1 - np.exp(np.mean(np.log(df_M["48ms"])))
geo_impr_64_M = 1 - np.exp(np.mean(np.log(df_M["64ms"])))

print(f"Geo-mean M improvement (48ms): {geo_impr_48_M*100:.2f}%")
print(f"Geo-mean M improvement (64ms): {geo_impr_64_M*100:.2f}%")


selected_improvements_M = []

for trace in df_M.index:
    chosen = selected_cfg[trace]
    if chosen == "32ms":
        continue   # skip baseline
    val = df_M.loc[trace, chosen]
    selected_improvements_M.append(val)

geo_selected_M = 1 - np.exp(np.mean(np.log(selected_improvements_M)))

print(f"Geo-mean M improvement (Selected t_REFI): {geo_selected_M*100:.2f}%")

#
geo_impr_48_refab = 1 - np.exp(np.mean(np.log(df_refab["48ms"])))
geo_impr_64_refab = 1 - np.exp(np.mean(np.log(df_refab["64ms"])))

print(f"Geo-mean REFab improvement (48ms): {geo_impr_48_refab*100:.2f}%")
print(f"Geo-mean REFab improvement (64ms): {geo_impr_64_refab*100:.2f}%")

selected_improvements_refab = []

for trace in df_refab.index:
    chosen = selected_cfg[trace]
    if chosen == "32ms":
        continue   # skip baseline
    val = df_refab.loc[trace, chosen]
    selected_improvements_refab.append(val)

geo_selected_refab = 1 - np.exp(np.mean(np.log(selected_improvements_refab)))

print(f"Geo-mean REFab improvement (Selected t_REFI): {geo_selected_refab*100:.2f}%")



# --- 4. Figure 5: Grouped Bar Chart of M_norm per Trace ---
plt.clf() # Use clf() instead of .figure() per guidelines
ax = df_M.plot(kind="bar", width=0.8, color=['#4C72B0', '#DD8452', '#55A868'], figsize=(9, 6))

for i, trace in enumerate(df_M.index):
    chosen = selected_cfg.get(trace)
    if chosen is None:
        continue

    cfg_index = CONFIGS.index(chosen)
    bar_index = cfg_index * len(df_M.index) + i
    bar = ax.patches[bar_index]

    ax.text(
        bar.get_x() + bar.get_width()/2,
        bar.get_height(),
        "★",
        ha='center',
        va='bottom',
        fontsize=10,
        color='gold'
    )

#plt.axhline(y=1.0, color='red', linestyle='--', alpha=0.5, label="32ms Baseline")
plt.ylabel(r"Normalized $M = E \cdot T^2$ per Trace Segment (vs 32ms-Baseline)")
plt.xlabel("Workload Trace")
plt.title("Performance-Energy Metric Comparison")
plt.legend(title="$tREFI$ Config", loc='lower right')
plt.xticks(rotation=45, ha='right')
plt.grid(axis='y', linestyle=':', alpha=0.7)

plt.tight_layout()
plt.savefig(Path(OUT_PATH) / "fig_M_comparison.png", dpi=300)

# --- 5. Figure 6: Scatter Plot (Energy vs. Latency Trade-off) ---
plt.clf()
colors = {'32ms': 'blue', '48ms': 'red', '64ms': 'green'}

for cfg in CONFIGS:
    sub = df_scatter[df_scatter["cfg"] == cfg]
    if sub.empty: continue
    plt.scatter(sub["lat_norm"], sub["energy_norm"], 
                label=cfg, color=colors.get(cfg), alpha=0.5, edgecolors='none', s = 20)

plt.axhline(y=1.0, color='black', linestyle='--', alpha=0.4)
plt.axvline(x=1.0, color='black', linestyle='--', alpha=0.4)
plt.xlabel("Normalized Avg Read Latency (vs 32ms-Baseline)")
plt.ylabel("Normalized Total Energy (vs 32ms-Baseline)")
plt.title("System Energy-Latency Trade-off")
plt.legend(title="$tREFI$ Config")
plt.grid(True, linestyle=':', alpha=0.4)

plt.tight_layout()
plt.savefig(Path(OUT_PATH) / "fig_tradeoff_energy_vs_latency.png", dpi=300)
plt.close()

# --- Figure: REFab Count Comparison ---
plt.clf()

ax = df_refab.plot(kind="bar", width=0.8, color=['#4C72B0', '#DD8452', '#55A868'], figsize=(9, 6))

for i, trace in enumerate(df_M.index):
    chosen = selected_cfg.get(trace)
    if chosen is None:
        continue

    cfg_index = CONFIGS.index(chosen)
    bar_index = cfg_index * len(df_M.index) + i
    bar = ax.patches[bar_index]

    ax.text(
        bar.get_x() + bar.get_width()/2,
        bar.get_height(),
        "★",
        ha='center',
        va='bottom',
        fontsize=10,
        color='gold'
    )
plt.ylabel("Normalized Average REFab Count per Trace Segment (vs 32ms-Baseline)")
plt.xlabel("Workload Trace")
plt.title("Refresh Operations Comparison")
plt.legend(title="$tREFI$ Config", loc='lower right')
plt.xticks(rotation=45, ha='right')
plt.grid(axis='y', linestyle=':', alpha=0.7)
plt.tight_layout()
plt.savefig(Path(OUT_PATH) / "fig_REFab_comparison.png", dpi=300)
plt.close()


print(f"Graphs saved successfully to {OUT_PATH}")
