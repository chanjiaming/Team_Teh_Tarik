#!/usr/bin/env python3
import os
import re
import math
import statistics
from collections import defaultdict, Counter
import numpy as np
import pandas as pd

# --- Configuration & Paths ---
BASE_PATH = os.path.expanduser('/home/eevee/Documents/team_teh_tarik/result')
AI_TRAINING_PATH = "/home/eevee/Documents/team_teh_tarik/Joshua_files"
FREQ_MHZ = 1600.0
CONFIGS = ['64ms', '96ms', '128ms']

# SER model params
FIT_PER_GB = 100.0         # 100 FIT / GB
DEVICE_Gb = 16.0 
EPS = 1e-30                # protect divide-by-zero
# Using the precise coefficients from your updated math
COEFF = { "64ms": 1.0, "96ms": 2.2628, "128ms": 4.0373 }
GAMMAS = np.arange(0.1, 0.25, 0.025)

# --- Regex Patterns (Performance & AI Features) ---
ENERGY_RE = re.compile(r"Total Energy ->\s*([\d\.eE\-\+]+)")
LAT_RE    = re.compile(r"avg_read_latency_0:\s*([\d\.]+)")
CYC_RE    = re.compile(r"memory_system_cycles:\s*([\d\.]+)")

# AI Feature Regex (Supports multiple log formats)
READ_RE   = re.compile(r"num_read_reqs_0:\s*([\d\.]+)|number_of_read_requests:\s*([\d\.]+)")
WRITE_RE  = re.compile(r"num_write_reqs_0:\s*([\d\.]+)|number_of_write_requests:\s*([\d\.]+)")
HITS_RE   = re.compile(r"row_hits_0:\s*([\d\.]+)|row_hits:\s*([\d\.]+)")
RMISS_RE  = re.compile(r"row_misses_0:\s*([\d\.]+)|row_misses:\s*([\d\.]+)")
RCONF_RE  = re.compile(r"row_conflicts_0:\s*([\d\.]+)|row_conflicts:\s*([\d\.]+)")
LLC_M_RE  = re.compile(r"llc_read_misses:\s*([\d\.]+)|cache_read_misses:\s*([\d\.]+)")
LLC_A_RE  = re.compile(r"llc_read_access:\s*([\d\.]+)|cache_read_access:\s*([\d\.]+)")

TRACE_DISPLAY_MAP = {
    'deepsjeng': 'Trace B (deepsjeng)',
    'mcf':       'Trace D (mcf)',
    'bwaves':    'Trace A (bwaves)',
    'x264':      'Trace F (x264)',
    'xz':        'Trace G (xz)',
    'gcc':       'Trace C (gcc)',
    'perlbench': 'Trace E (perlbench)',
}

def detect_trace_key(name: str) -> str:
    for key in TRACE_DISPLAY_MAP:
        if key in name: return key
    return name.split('_')[0] if '_' in name else name

def safe_float(regex, text, label=""):
    m = regex.search(text)
    if not m: return 0.0
    # Return the first non-None group (handles OR in regex)
    for group in m.groups():
        if group is not None: return float(group)
    return 0.0

def geomean(values):
    vals = [v for v in values if v > 0]
    return math.exp(sum(math.log(v) for v in vals) / len(vals)) if vals else float('nan')

def point_line_distance(px, py, ax, ay, bx, by):
    vx, vy = bx - ax, by - ay
    wx, wy = px - ax, py - ay
    denom = vx*vx + vy*vy
    if denom == 0: return math.hypot(px - ax, py - ay)
    return abs(vx*wy - vy*wx) / math.sqrt(denom)

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
                "LLC_Miss_Rate": l_miss / l_acc if l_acc > 0 else 0
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
            "runs": runs  # Keep raw runs for export
        }

valid_traces = [t for t in sorted(data.keys()) if all(c in data[t] for c in CONFIGS)]
if not valid_traces: raise SystemExit("No valid traces found.")

# --- 3. Pareto Sweep ---
gamma_results = []
per_gamma_selections = {}

for gamma in GAMMAS:
    selections, M_norms, ratio_norms, counts = {}, [], [], Counter()
    for t in valid_traces:
        M64, SER64 = data[t]["64ms"]["M"], max(data[t]["64ms"]["SER"], EPS)
        best_cfg, best_score, best_M, best_ratio = None, float("inf"), 0, 0

        for cfg in CONFIGS:
            M, SER = data[t][cfg]["M"], max(data[t][cfg]["SER"], EPS)
            ratio = SER / SER64
            # Score formula: Score = M * ratio * (COEFF^gamma)
            score = M * ratio * (COEFF[cfg] ** gamma)
            if score < best_score:
                best_score, best_cfg, best_M, best_ratio = score, cfg, M, ratio

        selections[t] = {"cfg": best_cfg, "M": best_M, "ratio": best_ratio}
        counts[best_cfg] += 1
        M_norms.append(best_M / M64)
        ratio_norms.append(best_ratio)

    gamma_results.append({
        "gamma": gamma, "M_impr": 1.0 - geomean(M_norms), "rel_deg_gm": geomean(ratio_norms),
        "M_norm_gm": geomean(M_norms), "counts": counts
    })
    per_gamma_selections[gamma] = selections

# Pick Pareto knee
gamma_results_sorted = sorted(gamma_results, key=lambda d: d["gamma"])
A, B = gamma_results_sorted[0], gamma_results_sorted[-1]
best = max(gamma_results_sorted, key=lambda r: point_line_distance(r["rel_deg_gm"], r["M_impr"], A["rel_deg_gm"], A["M_impr"], B["rel_deg_gm"], B["M_impr"]))

best_gamma = best["gamma"]
final_sel = per_gamma_selections[best_gamma]

# --- 4. Results & Export ---
print(f"\n=== Best Gamma: {best_gamma:.4f} ===")
for t in valid_traces:
    cfg = final_sel[t]["cfg"]
    print(f"- {t:20} -> {cfg}")

print("\n=== Exporting Scenarios for AI Training ===")
for t in valid_traces:
    winner_cfg = final_sel[t]["cfg"]
    save_path = os.path.join(AI_TRAINING_PATH, f"Scenario_{CONFIGS.index(winner_cfg) + 1}")
    os.makedirs(save_path, exist_ok=True)
    
    # Calculate additional risk metrics during export
    trace_export = []
    for run in data[t][winner_cfg]["runs"]:
        row = run.copy()
        row['Traffic_Risk'] = row['Incoming_Req_Per_Cycle'] * (1.0 - row['RB_Locality'])
        row['Conflict_Load'] = row['RB_Conflict_Rate'] * row['Read_Intensity']
        row['Label'] = winner_cfg
        trace_export.append(row)
        
    pd.DataFrame(trace_export).to_excel(os.path.join(save_path, f"trace_{t}.xlsx"), index=False)