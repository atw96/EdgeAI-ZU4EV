#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
# Retry export_design -flow syn with the clock frozen in 2020 so core_revision fits in int32.
# Target host: wsl-local. Waits until no vivado_hls is running.
set -euo pipefail
REPO=${EDGEAI_ROOT}
PRJ="$REPO/notebooks/hls4ml_prj"
OUT="$REPO/results/opt_v2/a1_shallow_syn.json"
LOG="$REPO/results/opt_v2/logs/a1_shallow_syn.log"
LIB="$REPO/results/opt_v2/libfakerev.so"
if [[ -f "$OUT" ]]; then
  echo "refuse overwrite $OUT" >&2
  exit 2
fi
gcc -shared -fPIC -O2 -o "$LIB" "$REPO/scripts/opt_v2/libfakerev.c" -ldl
echo "[$(date '+%F %T')] waiting for a free Vivado"
while pgrep -f 'vivado_hls|a1_shallow_csim.sh|p5_indexloop.sh' >/dev/null; do
  sleep 20
done
exec > >(tee -a "$LOG") 2>&1
echo "[$(date '+%F %T')] export_design -flow syn under frozen 2020 clock"
source /tools/Xilinx/Vivado/2020.1/settings64.sh
cd "$PRJ"
cat > export_syn.tcl <<'TCL'
open_project myproject_prj
open_solution solution1
export_design -rtl verilog -format ip_catalog -flow syn
exit
TCL
export LD_PRELOAD="$LIB"
/tools/Xilinx/Vivado/2020.1/bin/vivado_hls -f export_syn.tcl
unset LD_PRELOAD
python3 - <<'PY'
import json
from pathlib import Path
repo = Path(__import__("os").environ["EDGEAI_ROOT"])
root = repo / "notebooks/hls4ml_prj/myproject_prj/solution1"
rpts = [p for p in root.rglob("*.rpt") if "syn/report" not in str(p)]
print("non-csynth rpts", len(rpts))
for p in rpts[:30]:
    print(p)
text = ""
for p in rpts:
    if "util" in p.name.lower():
        text = p.read_text(errors="replace")
        print("USING", p)
        break
out = {"rpts": [str(p) for p in rpts[:40]], "util_excerpt": text[:4000]}
(repo / "results/opt_v2/a1_shallow_syn.json").write_text(json.dumps(out, indent=2) + "\n")
PY
echo "[$(date '+%F %T')] syn retry done"
