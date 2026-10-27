#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
H=${EDGEAI_ROOT}
python3 - <<'PY'
from pathlib import Path
for label, p in [
    ("P4", (Path(__import__("os").environ["EDGEAI_ROOT"]) / 'notebooks/hls4ml_prj.bak_bitexact_p1_narrow_p4/myproject_prj/solution1/syn/report/myproject_axi_csynth.rpt')),
    ("A1", (Path(__import__("os").environ["EDGEAI_ROOT"]) / 'notebooks/hls4ml_prj/myproject_prj/solution1/syn/report/myproject_axi_csynth.rpt')),
]:
    lines = p.read_text(errors="replace").splitlines()
    print("====", label, "exists", p.is_file(), "lines", len(lines))
    for i, line in enumerate(lines[:80]):
        if "Latency" in line or "Total" in line or "ap_clk" in line or "BRAM" in line:
            print(f"{i}: {line}")
PY
echo ----A1JSON----
cat "$H/results/opt_v2/a1_narrow_csynth.json"
echo ----P4MICRO----
ps -ef | grep -E 'p4_micro_csynth|p4_after' | grep -v grep | awk '{print $2,$8,$9}' || echo no_p4
tail -n 8 "$H/results/opt_v2/logs/p4_micro_csynth.log" 2>/dev/null || echo no_p4_log
