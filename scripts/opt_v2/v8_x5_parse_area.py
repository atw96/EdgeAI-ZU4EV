#!/usr/bin/env python3
import json
import re
from pathlib import Path

repo = Path(__file__).resolve().parents[2]
rpt = repo / "notebooks/hls4ml_prj_a2l/myproject_prj/solution1/syn/report/myproject_axi_csynth.rpt"
lines = rpt.read_text(errors="replace").splitlines()
avail = {}
instances = []
for line in lines:
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    if not cells:
        continue
    if cells[0] == "Available" and len(cells) >= 5:
        for k, c in zip(("BRAM_18K", "DSP48E", "FF", "LUT"), cells[1:5]):
            if re.fullmatch(r"[\d,]+", c):
                avail[k] = int(c.replace(",", ""))
    nums = [int(c.replace(",", "")) for c in cells if re.fullmatch(r"[\d,]+", c)]
    if cells[0].startswith("conv") or cells[0].startswith("dense") or "myproject" in cells[0]:
        if len(nums) >= 2:
            instances.append({"name": cells[0][:100], "max_cycles": max(nums)})
instances.sort(key=lambda r: r["max_cycles"], reverse=True)
out = {"available": avail, "longest": instances[:12]}
path = repo / "results/opt_v2/a2l/instances.json"
path.write_text(json.dumps(out, indent=2) + "\n")
print(json.dumps(out, indent=2)[:4000])
