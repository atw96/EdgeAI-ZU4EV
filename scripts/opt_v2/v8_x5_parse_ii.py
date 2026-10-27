#!/usr/bin/env python3
"""Pull ReuseLoop II and top latency from the parked A2-L csynth reports."""
import json
import re
from pathlib import Path

repo = Path(__file__).resolve().parents[2]
root = repo / "notebooks/hls4ml_prj_a2l/myproject_prj/solution1/syn/report"
rows = []
for rpt in sorted(root.glob("*_csynth.rpt")):
    text = rpt.read_text(errors="replace")
    if "ReuseLoop" not in text:
        continue
    # Achieved II sits in the loop table; take the first integer pair after ReuseLoop.
    for line in text.splitlines():
        if "ReuseLoop" not in line:
            continue
        nums = [int(x.replace(",", "")) for x in re.findall(r"\d[\d,]*", line)]
        rows.append({"report": rpt.name, "line": line.strip()[:240], "nums": nums[:8]})

top = root / "myproject_axi_csynth.rpt"
text = top.read_text(errors="replace")
lat = None
lines = text.splitlines()
for i, line in enumerate(lines):
    if "Latency (cycles)" not in line:
        continue
    for nxt in lines[i + 1 : i + 8]:
        cells = [c.strip() for c in nxt.strip().strip("|").split("|")]
        nums = [int(c.replace(",", "")) for c in cells if re.fullmatch(r"[\d,]+", c)]
        if len(nums) >= 2:
            lat = {"min": nums[0], "max": nums[1]}
            break
    if lat:
        break

ii_bad = []
for row in rows:
    nums = row["nums"]
    # HLS loop row: tripcount min/max, latency min/max, interval min/max, pipeline II achieved/target
    # achieved II is typically the last or second-to-last small integer. Record raw and flag if no 1.
    if 1 not in nums:
        ii_bad.append(row["report"])

out = {
    "top_latency": lat,
    "reuse_reports": len(rows),
    "ii_not_containing_1": ii_bad,
    "sample": rows[:12],
}
path = repo / "results/opt_v2/a2l/reuse_ii.json"
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(out, indent=2) + "\n")
print(json.dumps({"top": lat, "n": len(rows), "bad": ii_bad}, indent=2))
