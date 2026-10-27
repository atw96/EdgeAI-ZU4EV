#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
H=${EDGEAI_ROOT}
echo ----SLACK----
grep -n -E "WNS|WHS|Slack" "$H/impl_build.log" | grep -v '#' | head -30
echo ----RPT----
find "$H/vivado_project/EdgeAI_ZU4EV.runs/impl_1" -name '*timing*' -o -name '*util*' | head
python3 - <<'PY'
from pathlib import Path
root = (Path(__import__("os").environ["EDGEAI_ROOT"]) / 'vivado_project/EdgeAI_ZU4EV.runs/impl_1')
for p in root.rglob("*timing_summary*.rpt"):
    print("RPT", p, p.stat().st_size)
    text = p.read_text(errors="replace")
    for line in text.splitlines():
        if "WNS" in line or "WHS" in line or "Worst Negative" in line:
            print(line)
            break
for p in list(root.rglob("*utilization*.rpt"))[:3]:
    print("UTIL", p)
    for line in p.read_text(errors="replace").splitlines():
        if any(s in line for s in ("CLB LUTs*", "Block RAM Tile", "| DSPs", "Slice LUTs")):
            print(line)
PY
echo ----STATUS----
grep -n "write_bitstream\|impl_1:" "$H/results/opt_v2/logs/a1_impl.log" | grep -v '#' | tail -20
