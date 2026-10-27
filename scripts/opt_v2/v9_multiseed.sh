#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
set -euo pipefail
H=${EDGEAI_ROOT}
LOG=$H/results/opt_v2/logs/v9_multiseed.log
mkdir -p "$H/results/opt_v2/logs"
exec > >(tee -a "$LOG") 2>&1
echo "[$(date '+%F %T')] v9 multiseed"
if pgrep -x vivado >/dev/null; then
  echo VIVADO_BUSY
  exit 3
fi
cp -f ${EDGEAI_ROOT}/tcl/v9_multiseed.tcl /tmp/v9_multiseed.tcl
sed -i 's/\r$//' /tmp/v9_multiseed.tcl
source /tools/Xilinx/Vivado/2020.1/settings64.sh
cd "$H"
vivado -mode batch -source /tmp/v9_multiseed.tcl -log "$H/results/opt_v2/logs/v9_multiseed_vivado.log" -journal "$H/results/opt_v2/logs/v9_multiseed.jou"
echo "V9_MULTISEED_RC $?"
