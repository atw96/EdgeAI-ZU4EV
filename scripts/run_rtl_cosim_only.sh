#!/bin/bash
set -euo pipefail
REPO="/home/atw/Edge_AI_Acc/claude/EdgeAI-ZU4EV_Claude"
LOG="${REPO}/results/p1_rtl_cosim.log"
source ~/miniconda3/etc/profile.d/conda.sh
conda activate edgeai_39
cd "${REPO}/notebooks/hls4ml_prj"
exec >> "$LOG" 2>&1
echo "[$(date)] Starting RTL cosim..."
/tools/Xilinx/Vivado/2020.1/bin/vivado_hls -f build_prj.tcl reset=0 csim=0 synth=0 cosim=1 validation=0 export=0
echo "[$(date)] RTL cosim finished rc=$?"
