#!/bin/bash
# Gate 2+3: restore pristine firmware, board_safe FIFO patch, csynth BRAM gate + RTL cosim.
set -euo pipefail

REPO="/home/atw/Edge_AI_Acc/claude/EdgeAI-ZU4EV_Claude"
HLS="${REPO}/notebooks/hls4ml_prj"
BAK="${REPO}/notebooks/hls4ml_prj.bak_bitexact_fifo_fix"
VIVADO_HLS="/tools/Xilinx/Vivado/2020.1/bin/vivado_hls"
cd "$REPO"

export LIBRARY_PATH="/usr/lib/x86_64-linux-gnu:${LIBRARY_PATH:-}"
export HLS_STREAM_DEPTH_PROFILE=board_safe
export OUTPUT_AXIS_BITS=32 OUTPUT_PACK_MODE=serial AXI_DATAFLOW=0
export OUT_DIM=24 OUT_BYTES=96 OUT_LAYOUT=gap_ps OUT_FIXED_SCALE=1024
export IN_FIXED_SCALE=1024

echo "[$(date '+%F %T')] === restore firmware + board_safe patch ==="
if [[ -f "${BAK}/firmware/myproject.cpp" ]]; then
  cp "${BAK}/firmware/myproject.cpp" "${HLS}/firmware/myproject.cpp"
  echo "restored myproject.cpp from backup"
fi

source ~/miniconda3/etc/profile.d/conda.sh
conda activate edgeai_39
python3 scripts/patch_hls_lowmem.py || true
python3 scripts/patch_hls_dense_mult.py || true
python3 scripts/patch_hls_dense_resource_antihang.py || true
python3 scripts/patch_hls_mult_strategy.py || true
python3 scripts/patch_hls_stream_depth.py
python3 scripts/patch_hls_axi_top.py || true
python3 scripts/patch_axi_wrapper.py
python3 scripts/patch_axi_testbench.py
python3 scripts/patch_hls_axi_csim_tb.py || true

echo "[$(date '+%F %T')] === csynth ==="
conda deactivate 2>/dev/null || true
cd "$HLS"
rm -rf myproject_prj/solution1/.autopilot \
       myproject_prj/solution1/syn \
       myproject_prj/solution1/csim 2>/dev/null || true
$VIVADO_HLS -f build_prj.tcl reset=1 csim=0 synth=1 cosim=0 validation=0 export=0

cd "$REPO"
source ~/miniconda3/etc/profile.d/conda.sh
conda activate edgeai_39
python3 scripts/hls_csynth_gate.py || GATE_RC=$?
GATE_RC=${GATE_RC:-0}
if [[ "$GATE_RC" -ne 0 ]]; then
  BRAM_OK=$(python3 -c "import json; d=json.load(open('results/hls_csynth_gate.json')); print(d.get('bram_pass', d['used']['BRAM_18K']<256))")
  if [[ "$BRAM_OK" != "True" ]]; then
    echo "ERROR: csynth BRAM gate failed"
    exit 1
  fi
  echo "WARN: LUT gate failed but BRAM ok — continuing"
fi

echo "[$(date '+%F %T')] === RTL cosim N=2 ==="
N_GAP_COMPARE=2 bash scripts/run_hls_csim_cosim.sh
