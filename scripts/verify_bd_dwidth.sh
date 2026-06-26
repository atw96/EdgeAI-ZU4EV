#!/bin/bash
# Quick check: create_block_design.tcl produces axis_dw_s2mm in system.bd
set -euo pipefail
REPO="/home/atw/Edge_AI_Acc/claude/EdgeAI-ZU4EV_Claude"
source /tools/Xilinx/Vivado/2020.1/settings64.sh
cd "$REPO"
vivado -mode batch -nojournal -nolog -source tcl/create_block_design.tcl 2>&1 | tee results/verify_bd_dwidth.log
if grep -q axis_dw_s2mm vivado_project/EdgeAI_ZU4EV.srcs/sources_1/bd/system/system.bd; then
    echo "OK: axis_dw_s2mm present in system.bd"
    exit 0
fi
echo "FAIL: axis_dw_s2mm missing from system.bd"
exit 1
