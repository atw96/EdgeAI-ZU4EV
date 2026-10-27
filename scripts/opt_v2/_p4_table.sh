#!/bin/bash
python3 - <<'PY'
import json
from pathlib import Path
p = (Path(__import__("os").environ["EDGEAI_ROOT"]) / 'results/opt_v2/p4_micro_csynth.json')
d = json.loads(p.read_text())
for c in d["cases"]:
    lat = c["top_latency_cycles_max"]
    theory = c["theory_cycles_1024_times_rf"]
    padded = int(round(theory * 1156 / 1024))
    print(f"{c['name']:22} lat={lat:7} theory={theory:7} padded={padded:7} "
          f"lat/padded={lat/padded:.3f} ii={c['final_ii']} LUT={c['util'].get('LUT')} BRAM={c['util'].get('BRAM_18K')}")
PY
