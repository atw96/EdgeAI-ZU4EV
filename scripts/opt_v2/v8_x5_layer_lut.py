#!/usr/bin/env python3
from pathlib import Path
root = (Path(__file__).resolve().parents[2] / 'notebooks/hls4ml_prj_a2l/myproject_prj/solution1/syn/report')
rows = []
for rpt in root.glob("*_csynth.rpt"):
    lines = rpt.read_text(errors="replace").splitlines()
    lut = None
    for i, line in enumerate(lines):
        if line.strip().startswith("|Total"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) >= 5 and cells[4].replace(",", "").isdigit():
                lut = int(cells[4].replace(",", ""))
                break
    if lut is not None:
        rows.append((lut, rpt.name))
rows.sort(reverse=True)
for lut, name in rows[:12]:
    print(f"{lut:8d}  {name[:100]}")
print("ip", (Path(__file__).resolve().parents[2] / 'notebooks/hls4ml_prj_a2l/myproject_prj/solution1/impl/ip').exists())
