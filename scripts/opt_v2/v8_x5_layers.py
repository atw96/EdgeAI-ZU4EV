#!/usr/bin/env python3
import re
from pathlib import Path

root = (Path(__file__).resolve().parents[2] / 'notebooks/hls4ml_prj_a2l/myproject_prj/solution1/syn/report')
rows = []
for rpt in sorted(root.glob("*_csynth.rpt")):
    lines = rpt.read_text(errors="replace").splitlines()
    lat = None
    for i, line in enumerate(lines):
        if "Latency (cycles)" not in line or "Instance" in line:
            continue
        for nxt in lines[i + 1 : i + 6]:
            cells = [c.strip() for c in nxt.strip().strip("|").split("|")]
            nums = [int(c.replace(",", "")) for c in cells if re.fullmatch(r"[\d,]+", c)]
            if len(nums) >= 2:
                lat = nums[1]
                break
        if lat is not None:
            break
    if lat is not None:
        rows.append((lat, rpt.name))
rows.sort(reverse=True)
for lat, name in rows[:15]:
    print(f"{lat:8d}  {name[:110]}")
# raw instance lines containing myproject
top = (root / "myproject_axi_csynth.rpt").read_text(errors="replace").splitlines()
print("--- instance lines ---")
for line in top:
    if "myproject_U0" in line or line.strip().startswith("|conv"):
        print(line[:220])
