#!/usr/bin/env python3
"""Print the utilization tables from the A2-L and restored RC1 csynth reports."""
from pathlib import Path

pairs = [
    ("a2l", (Path(__file__).resolve().parents[2] / 'notebooks/hls4ml_prj_a2l/myproject_prj/solution1/syn/report/myproject_axi_csynth.rpt')),
    ("rc1", (Path(__file__).resolve().parents[2] / 'notebooks/hls4ml_prj/myproject_prj/solution1/syn/report/myproject_axi_csynth.rpt')),
]
for name, rpt in pairs:
    print("====", name, rpt.exists(), "====")
    if not rpt.exists():
        continue
    lines = rpt.read_text(errors="replace").splitlines()
    grab = False
    n = 0
    for line in lines:
        if "Utilization Estimates" in line or "|Total" in line.replace(" ", "") or line.strip().startswith("|    Total") or "BRAM_18K" in line:
            grab = True
        if grab:
            print(line[:200])
            n += 1
            if n > 25:
                break
