#!/usr/bin/env python3
import os
import re
import math
import statistics
from collections import defaultdict, Counter
import numpy as np

BASE_PATH = os.path.expanduser('/home/eevee/Documents/team_teh_tarik/result')
FREQ_MHZ = 1600.0
CONFIGS = ['64ms', '96ms', '128ms']

# SER model params (your assumptions)
FIT_PER_GB = 100.0         # 100 FIT / GB
DEVICE_Gb = 16.0 
EPS = 1e-30                # protect divide-by-zero for tiny SER
COEFF = {
    "64ms": 1.0,
    "96ms": 2.2628,
    "128ms": 4.0373
}

GAMMAS = np.arange(0.1, 0.25, 0.025)
for gamma in GAMMAS:
    print(f"Evaluating gamma={gamma}...")
#GAMMAS = [round(x, 2) for x in [0.00, 0.02, 0.05, 0.08, 0.10, 0.12, 0.15, 0.18, 0.20, 0.25, 0.30]]

TRACE_DISPLAY_MAP = {
    'deepsjeng': 'Trace B (deepsjeng)',
    'mcf':       'Trace D (mcf)',
    'bwaves':    'Trace A (bwaves)',
    'x264':      'Trace F (x264)',
    'xz':        'Trace G (xz)',
    'gcc':       'Trace C (gcc)',
    'perlbench': 'Trace E (perlbench)',
}

ENERGY_RE = re.compile(r"Total Energy ->\s*([\d\.eE\-\+]+)")
LAT_RE    = re.compile(r"avg_read_latency_0:\s*([\d\.]+)")
CYC_RE    = re.compile(r"memory_system_cycles:\s*([\d\.]+)")

def detect_trace_key(name: str) -> str:
    for key in TRACE_DISPLAY_MAP:
        if key in name:
            return key
    return name.split('_')[0] if '_' in name else name

def safe_float(regex, text, label=""):
    m = regex.search(text)
    if not m:
        raise ValueError(f"Pattern not found ({label}): {regex.pattern}")
    return float(m.group(1))

def geomean(values):
    # geometric mean of positive values
    vals = [v for v in values if v > 0]
    if not vals:
        return float('nan')
    return math.exp(sum(math.log(v) for v in vals) / len(vals))

def point_line_distance(px, py, ax, ay, bx, by):
    # distance from P to line through A-B in 2D
    # if A==B, fallback to euclidean distance to A
    vx, vy = bx - ax, by - ay
    wx, wy = px - ax, py - ay
    denom = vx*vx + vy*vy
    if denom == 0:
        return math.hypot(px - ax, py - ay)
    # perpendicular distance magnitude using cross product / |v|
    cross = abs(vx*wy - vy*wx)
    return cross / math.sqrt(denom)

print(f"Scanning: {BASE_PATH}")

# Collect candidate trace roots (folders that contain cfg subfolders)
trace_roots = set()
for root, dirs, _files in os.walk(BASE_PATH):
    if any(any(cfg in d for cfg in CONFIGS) for d in dirs):
        trace_roots.add(root)

# aggregated[trace_key][cfg] = list of runs (to average if duplicates exist)
aggregated = defaultdict(lambda: {cfg: [] for cfg in CONFIGS})

for trace_path in sorted(trace_roots):
    trace_key = detect_trace_key(os.path.basename(trace_path))

    for cfg in CONFIGS:
        # find a folder inside trace_path containing cfg substring
        try:
            cfg_folder = next((d for d in os.listdir(trace_path) if cfg in d), None)
        except FileNotFoundError:
            continue
        if not cfg_folder:
            continue

        full_path = os.path.join(trace_path, cfg_folder)
        if not os.path.isdir(full_path):
            continue

        dp_file  = next((f for f in os.listdir(full_path) if 'drampower_report' in f), None)
        ram_file = next((f for f in os.listdir(full_path) if 'ramulator2_report' in f), None)
        if not dp_file or not ram_file:
            continue

        try:
            with open(os.path.join(full_path, dp_file), 'r') as f:
                dp_txt = f.read()
                E = safe_float(ENERGY_RE, dp_txt, "Total Energy")

            with open(os.path.join(full_path, ram_file), 'r') as f:
                ram_txt = f.read()
                lat_cyc = safe_float(LAT_RE, ram_txt, "avg_read_latency_0")
                tot_cyc = safe_float(CYC_RE, ram_txt, "memory_system_cycles")

            freq_hz = FREQ_MHZ * 1e6
            lat_sec = lat_cyc / freq_hz
            duration_hours = (tot_cyc / freq_hz) / 3600.0

            # M = E * T^2
            M = E * (lat_sec ** 2)

            # SER model from FIT/GB
            mu = (FIT_PER_GB / 1e9) * DEVICE_Gb * duration_hours
            SER = 1.0 - math.exp(-mu)

            aggregated[trace_key][cfg].append({
                "E": E,
                "lat_cyc": lat_cyc,
                "lat_sec": lat_sec,
                "tot_cyc": tot_cyc,
                "hours": duration_hours,
                "M": M,
                "SER": SER,
                "path": full_path,
            })

        except Exception as e:
            print(f"[WARN] {trace_key} {cfg}: {e}")
            continue

# Average per trace×cfg (in case multiple chunks exist)
data = defaultdict(dict)
for trace_key, cfgs in aggregated.items():
    for cfg, runs in cfgs.items():
        if not runs:
            continue
        # mean of key metrics
        data[trace_key][cfg] = {
            "M": statistics.mean(r["M"] for r in runs),
            "SER": statistics.mean(r["SER"] for r in runs),
            "E": statistics.mean(r["E"] for r in runs),
            "lat_sec": statistics.mean(r["lat_sec"] for r in runs),
            "hours": statistics.mean(r["hours"] for r in runs),
            "n_runs": len(runs),
        }

# Filter traces that have all 3 configs and baseline present
valid_traces = []
for t in sorted(data.keys()):
    if all(cfg in data[t] for cfg in CONFIGS) and data[t]["64ms"]["M"] > 0:
        valid_traces.append(t)

if not valid_traces:
    raise SystemExit("No valid traces found with complete 64/96/128ms runs.")

print(f"Found {len(valid_traces)} valid traces: {valid_traces}")

# Evaluate each gamma
gamma_results = []
per_gamma_selections = {}

for gamma in GAMMAS:
    selections = {}
    M_norms = []
    ratio_norms = []
    counts = Counter()

    for t in valid_traces:
        M64 = data[t]["64ms"]["M"]
        SER64 = max(data[t]["64ms"]["SER"], EPS)

        best_cfg = None
        best_score = float("inf")
        best_ratio = None
        best_M = None

        for cfg in CONFIGS:
            M = data[t][cfg]["M"]
            SER = max(data[t][cfg]["SER"], EPS)
            ratio = SER / SER64

            coefficient = COEFF[cfg]
            score = M * ratio*(coefficient ** gamma)
            if score < best_score:
                best_score = score
                best_cfg = cfg
                best_ratio = ratio
                best_M = M

        selections[t] = {
            "cfg": best_cfg,
            "score": best_score,
            "M": best_M,
            "ratio": best_ratio
        }
        counts[best_cfg] += 1

        M_norms.append(best_M / M64)
        ratio_norms.append(best_ratio)

    # suite-level summaries
    M_norm_gm = geomean(M_norms)                 # < 1 is better
    M_impr = 1.0 - M_norm_gm                     # higher is better
    rel_deg_gm = geomean(ratio_norms)            # >= 1, lower is better

    gamma_results.append({
        "gamma": gamma,
        "M_norm_gm": M_norm_gm,
        "M_impr": M_impr,
        "rel_deg_gm": rel_deg_gm,
        "count_64": counts["64ms"],
        "count_96": counts["96ms"],
        "count_128": counts["128ms"],
    })
    per_gamma_selections[gamma] = selections

# Pick best gamma by Pareto knee on (x=rel_deg_gm, y=M_impr)
# endpoints = most aggressive (min gamma) and most conservative (max gamma)
gamma_results_sorted = sorted(gamma_results, key=lambda d: d["gamma"])
A = gamma_results_sorted[0]
B = gamma_results_sorted[-1]
ax, ay = A["rel_deg_gm"], A["M_impr"]
bx, by = B["rel_deg_gm"], B["M_impr"]

best = None
best_dist = -1.0
for r in gamma_results_sorted:
    px, py = r["rel_deg_gm"], r["M_impr"]
    d = point_line_distance(px, py, ax, ay, bx, by)
    if d > best_dist:
        best_dist = d
        best = r

best_gamma = best["gamma"]
final_sel = per_gamma_selections[best_gamma]

# Print summary
print("\n=== Gamma Sweep Summary ===")
print("gamma | geoM(M_sel/M64) | geoM(rel_deg) | geoM M_impr | #64 #96 #128")
for r in gamma_results_sorted:
    print(f"{r['gamma']:<5} | {r['M_norm_gm']:.6g}        | {r['rel_deg_gm']:.6g}     | {r['M_impr']:.4f}    | "
          f"{r['count_64']:>3} {r['count_96']:>4} {r['count_128']:>4}")

print(f"\n=== Selected Best Gamma (Pareto knee) ===")
print(f"best_gamma = {best_gamma}  (max distance to end-to-end tradeoff line = {best_dist:.6g})")
print(f"Suite geoM(M_sel/M64) = {best['M_norm_gm']:.6g}  => geoM M improvement = {best['M_impr']:.4f}")
print(f"Suite geoM(rel_deg)   = {best['rel_deg_gm']:.6g}")

print("\n=== Final t_REFI Selection per Trace (using best_gamma) ===")
for t in valid_traces:
    disp = TRACE_DISPLAY_MAP.get(t, t)
    cfg = final_sel[t]["cfg"]
    ratio = final_sel[t]["ratio"]
    mnorm = final_sel[t]["M"] / data[t]["64ms"]["M"]
    print(f"- {disp:25s} -> {cfg:5s} | M_sel/M64={mnorm:.4f} | SER_ratio={ratio:.4f}")
