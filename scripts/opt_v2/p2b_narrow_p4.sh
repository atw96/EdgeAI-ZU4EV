#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
# P2b: csynth the narrow P4 project in place, then record r = 57.43 / csynth_ms.
# Does not touch the live A1' tree. Refuses to start while the 1k csim script holds projects.
# Target host: wsl-local.
set -euo pipefail
REPO=${EDGEAI_ROOT}
P4="$REPO/notebooks/hls4ml_prj.bak_bitexact_p1_narrow_p4"
OUT="$REPO/results/opt_v2/p2b_narrow_p4.json"
LOG="$REPO/results/opt_v2/logs/p2b_narrow_p4.log"
if [[ -f "$OUT" ]]; then
  echo "refuse overwrite $OUT" >&2
  exit 2
fi
if pgrep -f 'p1_narrow_1k.sh|p1_fix_continue.sh' >/dev/null; then
  echo "csim still running" >&2
  exit 3
fi
test -f "$P4/build_prj.tcl"
exec > >(tee -a "$LOG") 2>&1
echo "[$(date '+%F %T')] P2b csynth narrow P4"
source /tools/Xilinx/Vivado/2020.1/settings64.sh
cd "$P4"
rm -rf myproject_prj/solution1/.autopilot myproject_prj/solution1/syn
/tools/Xilinx/Vivado/2020.1/bin/vivado_hls -f build_prj.tcl reset=1 csim=0 synth=1 cosim=0 validation=0 export=0
python3 - <<'PY'
import json, re
from pathlib import Path
repo = Path(__import__("os").environ["EDGEAI_ROOT"])
rpt = repo / "notebooks/hls4ml_prj.bak_bitexact_p1_narrow_p4/myproject_prj/solution1/syn/report/myproject_axi_csynth.rpt"
text = rpt.read_text(errors="replace")
# first latency table: max latency in cycles is the first integer after "Latency (cycles)"
# Summary data row: | min_cyc | max_cyc | min_abs | max_abs | interval...
lat = None
lines = text.splitlines()
for i, line in enumerate(lines):
    if "Latency (cycles)" not in line:
        continue
    for nxt in lines[i+1:i+8]:
        if "ms" not in nxt:
            continue
        cells = [c.strip() for c in nxt.strip().strip("|").split("|")]
        nums = [int(c.replace(",", "")) for c in cells if re.fullmatch(r"[\d,]+", c)]
        if len(nums) >= 2:
            lat = nums[1]
            break
    if lat:
        break
util = {}
for line in lines:
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    if cells and cells[0] == "Total" and len(cells) >= 6:
        keys = ("BRAM_18K", "DSP48E", "FF", "LUT", "URAM")
        for k, c in zip(keys, cells[1:6]):
            if re.fullmatch(r"[\d,]+", c):
                util[k] = int(c.replace(",", ""))
        break
clk = 5.0
ms = None if lat is None else lat * clk / 1e6
board = 57.43
r = None if not ms else board / ms
out = {
    "project": "hls4ml_prj.bak_bitexact_p1_narrow_p4",
    "precision": "BIT_EXACT=0 route1 narrow",
    "variant": "P4",
    "top_latency_cycles_max": lat,
    "clock_ns": clk,
    "csynth_ms": ms,
    "board_ms": board,
    "r_board_over_csynth": r,
    "util": util,
    "report": str(rpt),
}
path = repo / "results/opt_v2/p2b_narrow_p4.json"
path.write_text(json.dumps(out, indent=2) + "\n")
print(json.dumps(out, indent=2))
PY
echo "[$(date '+%F %T')] P2b done"
