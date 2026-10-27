#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
# P5: IndexLoop II=1 on a copy of the narrow P4 project. The original tree stays unpatched.
# Target host: wsl-local.
set -euo pipefail
REPO=${EDGEAI_ROOT}
SRC="$REPO/notebooks/hls4ml_prj.bak_bitexact_p1_narrow_p4"
DEST="$REPO/results/opt_v2/p5_p4_prj"
OUT="$REPO/results/opt_v2/p5_indexloop.json"
LOG="$REPO/results/opt_v2/logs/p5_indexloop.log"
if [[ -f "$OUT" ]]; then
  echo "refuse overwrite $OUT" >&2
  exit 2
fi
if pgrep -f vivado_hls >/dev/null; then
  echo "vivado busy" >&2
  exit 3
fi
rm -rf "$DEST"
mkdir -p "$DEST"
# firmware and tcl only; csynth rebuilds the solution
cp -a "$SRC/firmware" "$SRC/build_prj.tcl" "$DEST/"
if [[ -f "$SRC/project.tcl" ]]; then cp -a "$SRC/project.tcl" "$DEST/"; fi
if [[ -f "$SRC/myproject_test.cpp" ]]; then cp -a "$SRC/myproject_test.cpp" "$DEST/"; fi
python3 "$REPO/scripts/opt_v2/patch_hls_indexloop.py" \
  "$DEST/firmware/nnet_utils/nnet_dense_resource.h"
exec > >(tee -a "$LOG") 2>&1
echo "[$(date '+%F %T')] P5 csynth"
source /tools/Xilinx/Vivado/2020.1/settings64.sh
cd "$DEST"
/tools/Xilinx/Vivado/2020.1/bin/vivado_hls -f build_prj.tcl reset=1 csim=0 synth=1 cosim=0 validation=0 export=0
python3 - <<'PY'
import json, re
from pathlib import Path
repo = Path(__import__("os").environ["EDGEAI_ROOT"])
rpt = repo / "results/opt_v2/p5_p4_prj/myproject_prj/solution1/syn/report/myproject_axi_csynth.rpt"
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
base = 675391
out = {
    "change": "PIPELINE II=1 on IndexLoop in dense_resource_rf_gt_nin_rem0",
    "baseline_unpatched_cycles": base,
    "patched_cycles": lat,
    "csynth_ms": None if lat is None else lat * 5.0 / 1e6,
    "ratio_to_unpatched": None if not lat else lat / base,
    "h1_holds": bool(lat is not None and lat < 0.9 * base),
    "util": util,
    "report": str(rpt),
}
path = repo / "results/opt_v2/p5_indexloop.json"
path.write_text(json.dumps(out, indent=2) + "\n")
print(json.dumps(out, indent=2))
PY
echo "[$(date '+%F %T')] P5 done"
