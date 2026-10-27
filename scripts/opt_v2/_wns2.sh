#!/bin/bash
python3 - <<'PY'
from pathlib import Path
p = (Path(__import__("os").environ["EDGEAI_ROOT"]) / 'vivado_project/EdgeAI_ZU4EV.runs/impl_1/system_wrapper_timing_summary_routed.rpt')
lines = p.read_text(errors="replace").splitlines()
for i, line in enumerate(lines):
    if "WNS(ns)" in line and "TNS" in line:
        print(line)
        # next non-empty, non-dash line
        for nxt in lines[i+1:i+8]:
            if nxt.strip() and not set(nxt.strip()) <= set("+-| "):
                print(nxt)
                break
        break
u = (Path(__import__("os").environ["EDGEAI_ROOT"]) / 'vivado_project/EdgeAI_ZU4EV.runs/impl_1/system_wrapper_utilization_placed.rpt')
for line in u.read_text(errors="replace").splitlines():
    if any(s in line for s in ("CLB LUTs*", "LUT as Logic", "Block RAM Tile", "| DSPs", "Slice LUTs*")):
        print(line)
PY
