#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
set -euo pipefail
H=${EDGEAI_ROOT}
cp -f ${EDGEAI_ROOT}/tcl/v9_period.tcl /tmp/v9_period.tcl
sed -i 's/\r$//' /tmp/v9_period.tcl
source /tools/Xilinx/Vivado/2020.1/settings64.sh
cd "$H"
vivado -mode batch -source /tmp/v9_period.tcl -log "$H/results/opt_v2/logs/v9_period_vivado.log" -journal "$H/results/opt_v2/logs/v9_period.jou"
echo PERIOD_RC $?
