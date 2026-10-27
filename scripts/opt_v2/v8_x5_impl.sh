#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
# Copy the RC1 Vivado project and place/route A2-L. Does not open the RC1 project.
set -euo pipefail
H=${EDGEAI_ROOT}
M=${EDGEAI_ROOT}
LOG=$H/results/opt_v2/logs/v8_x5_impl.log
mkdir -p "$H/results/opt_v2/logs" "$H/results/opt_v2/a2l"
exec > >(tee -a "$LOG") 2>&1
echo "[$(date '+%F %T')] x5 impl"
if pgrep -x vivado >/dev/null; then
  echo VIVADO_BUSY
  exit 3
fi
if [ ! -d "$H/vivado_project_a2l" ]; then
  cp -a "$H/vivado_project" "$H/vivado_project_a2l"
  python3 - << 'PY'
from pathlib import Path
p = (Path(__import__("os").environ["EDGEAI_ROOT"]) / 'vivado_project_a2l/EdgeAI_ZU4EV.xpr')
t = p.read_text()
old = "/vivado_project/EdgeAI_ZU4EV.xpr"
new = "/vivado_project_a2l/EdgeAI_ZU4EV.xpr"
if old not in t:
    raise SystemExit("COPY_PATH_MISSING")
p.write_text(t.replace(old, new, 1))
PY
fi
grep -q '/vivado_project/EdgeAI_ZU4EV.xpr' "$H/vivado_project/EdgeAI_ZU4EV.xpr"
grep -q '/vivado_project_a2l/EdgeAI_ZU4EV.xpr' "$H/vivado_project_a2l/EdgeAI_ZU4EV.xpr"
cp -f "$M/tcl/x5_a2l_impl.tcl" /tmp/x5_a2l_impl.tcl
sed -i 's/\r$//' /tmp/x5_a2l_impl.tcl
source /tools/Xilinx/Vivado/2020.1/settings64.sh
cd "$H"
vivado -mode batch -source /tmp/x5_a2l_impl.tcl -log "$H/results/opt_v2/logs/x5_a2l_vivado.log" -journal "$H/results/opt_v2/logs/x5_a2l.jou"
echo "A2L_IMPL_RC $?"
