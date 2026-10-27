#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
# Csynth the narrow A1' project that passed the numeric gate.
# Target host: wsl-local. Does not run until called, and refuses a P4 reuse table.
set -euo pipefail
REPO=${EDGEAI_ROOT}
PRJ="$REPO/notebooks/hls4ml_prj"
OUT="$REPO/results/opt_v2/a1_narrow_csynth.json"
LOG="$REPO/results/opt_v2/logs/a1_narrow_csynth.log"
if [[ -f "$OUT" ]]; then
  echo "refuse overwrite $OUT" >&2
  exit 2
fi
if pgrep -f 'p2b_narrow_p4.sh|vivado_hls' >/dev/null; then
  echo "vivado still busy" >&2
  exit 3
fi
python3 - <<'PY'
import re
from pathlib import Path
t = (Path(__import__("os").environ["EDGEAI_ROOT"]) / 'notebooks/hls4ml_prj/firmware/parameters.h').read_text()
rfs = [int(x) for x in re.findall(r"reuse_factor\s*=\s*(\d+)", t)]
print("reuse_factors", rfs[:12])
if not rfs or rfs[0] != 27:
    raise SystemExit("expected A1' conv1a reuse_factor 27, got %s" % (rfs[:1],))
PY
exec > >(tee -a "$LOG") 2>&1
echo "[$(date '+%F %T')] csynth narrow A1'"
source /tools/Xilinx/Vivado/2020.1/settings64.sh
cd "$PRJ"
rm -rf myproject_prj/solution1/.autopilot myproject_prj/solution1/syn
/tools/Xilinx/Vivado/2020.1/bin/vivado_hls -f build_prj.tcl reset=1 csim=0 synth=1 cosim=0 validation=0 export=0
python3 - <<'PY'
import json, re
from pathlib import Path
repo = Path(__import__("os").environ["EDGEAI_ROOT"])
rpt = repo / "notebooks/hls4ml_prj/myproject_prj/solution1/syn/report/myproject_axi_csynth.rpt"
text = rpt.read_text(errors="replace")
lines = text.splitlines()
lat = None
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
        for k, c in zip(("BRAM_18K", "DSP48E", "FF", "LUT", "URAM"), cells[1:6]):
            if re.fullmatch(r"[\d,]+", c):
                util[k] = int(c.replace(",", ""))
        break
clk = 5.0
ms = None if lat is None else lat * clk / 1e6
out = {
    "project": "notebooks/hls4ml_prj",
    "precision": "BIT_EXACT=0 route1 narrow",
    "variant": "A1prime",
    "top_latency_cycles_max": lat,
    "clock_ns": clk,
    "csynth_ms": ms,
    "util": util,
    "device": {"LUT": 87840, "BRAM_18K": 256, "DSP48E": 728, "URAM": 48},
    "over_device": bool(util.get("LUT", 0) > 87840 or util.get("BRAM_18K", 0) > 256),
    "report": str(rpt),
}
path = repo / "results/opt_v2/a1_narrow_csynth.json"
path.write_text(json.dumps(out, indent=2) + "\n")
print(json.dumps(out, indent=2))
PY
echo "[$(date '+%F %T')] narrow A1' csynth done"
