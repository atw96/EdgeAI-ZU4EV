#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
# Shallow the narrow A1' FIFOs with the existing aggressive profile, then csynth.
# If the estimate is still over the device, run export_design -flow syn.
# Target host: wsl-local.
set -euo pipefail
REPO=${EDGEAI_ROOT}
PRJ="$REPO/notebooks/hls4ml_prj"
OUT="$REPO/results/opt_v2/a1_shallow_csynth.json"
LOG="$REPO/results/opt_v2/logs/a1_shallow_csynth.log"
if [[ -f "$OUT" ]]; then
  echo "refuse overwrite $OUT" >&2
  exit 2
fi
if pgrep -f vivado_hls >/dev/null; then
  echo "vivado busy" >&2
  exit 3
fi
cp -a "$PRJ/firmware/myproject.cpp" "$REPO/results/opt_v2/a1_myproject_deep_fifo.cpp"
cd "$REPO"
python3 scripts/patch_hls_stream_depth.py
python3 - <<'PY'
import re
from collections import Counter
from pathlib import Path
t = (Path(__import__("os").environ["EDGEAI_ROOT"]) / 'notebooks/hls4ml_prj/firmware/myproject.cpp').read_text()
print("depths", Counter(re.findall(r"depth=(\d+)", t)))
PY
exec > >(tee -a "$LOG") 2>&1
echo "[$(date '+%F %T')] csynth A1' with aggressive FIFO depths"
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
out = {
    "project": "notebooks/hls4ml_prj",
    "change": "patch_hls_stream_depth.py profile=aggressive; kernel_data partition left complete",
    "top_latency_cycles_max": lat,
    "clock_ns": 5.0,
    "csynth_ms": None if lat is None else lat * 5.0 / 1e6,
    "util": util,
    "over_device": bool(util.get("LUT", 0) > 87840 or util.get("BRAM_18K", 0) > 256),
    "report": str(rpt),
}
path = repo / "results/opt_v2/a1_shallow_csynth.json"
path.write_text(json.dumps(out, indent=2) + "\n")
print(json.dumps(out, indent=2))
PY
set +e
python3 - <<'PY'
import json
from pathlib import Path
repo = Path(__import__("os").environ["EDGEAI_ROOT"])
d = json.loads((repo / "results/opt_v2/a1_shallow_csynth.json").read_text())
if not d["over_device"]:
    print("under device, skip export_design syn")
    raise SystemExit(0)
print("still over device, export_design -flow syn")
raise SystemExit(10)
PY
syn_rc=$?
set -e
if [[ "$syn_rc" == "10" ]]; then
  cat > "$PRJ/export_syn.tcl" <<'TCL'
open_project myproject_prj
open_solution solution1
export_design -rtl verilog -format ip_catalog -flow syn
exit
TCL
  /tools/Xilinx/Vivado/2020.1/bin/vivado_hls -f export_syn.tcl
  python3 - <<'PY'
import json
from pathlib import Path
repo = Path(__import__("os").environ["EDGEAI_ROOT"])
root = repo / "notebooks/hls4ml_prj/myproject_prj/solution1"
hits = sorted(root.rglob("*util*")) + sorted(root.rglob("*export*.rpt"))
print("syn reports:")
for p in hits:
    if p.is_file() and p.stat().st_size < 5_000_000:
        print(p, p.stat().st_size)
PY
fi
echo "[$(date '+%F %T')] shallow A1' done"
