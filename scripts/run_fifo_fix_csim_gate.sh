#!/bin/bash
# Gate 1: patches + csim N=100 after fifo/RF fix convert.
set -euo pipefail

REPO="/home/atw/Edge_AI_Acc/claude/EdgeAI-ZU4EV_Claude"
cd "$REPO"
source ~/miniconda3/etc/profile.d/conda.sh
conda activate edgeai_39

export OUTPUT_AXIS_BITS=32 OUTPUT_PACK_MODE=serial AXI_DATAFLOW=0
export OUT_DIM=24 OUT_BYTES=96 OUT_LAYOUT=gap_ps OUT_FIXED_SCALE=1024
export IN_FIXED_SCALE=1024 BIT_EXACT=0
export HLS_STREAM_DEPTH_PROFILE=board_safe
export DENSE_NPZ="${REPO}/deploy/dense_head.npz"
export SKIP_BOARD=1 N_GAP_COMPARE=100 N_ACCURACY=100

python3 scripts/patch_hls_lowmem.py || true
python3 scripts/patch_hls_dense_mult.py || true
python3 scripts/patch_hls_dense_resource_antihang.py || true
python3 scripts/patch_hls_mult_strategy.py || true
python3 scripts/patch_hls_stream_depth.py
python3 scripts/patch_hls_axi_top.py || true
python3 scripts/patch_axi_wrapper.py
python3 scripts/patch_axi_testbench.py
python3 scripts/patch_hls_axi_csim_tb.py || true

bash scripts/run_gap_axi_csim.sh 2>&1 | tee results/v19_fifo_fix_csim.log

N_ACCURACY=100 OUT_DIM=24 DENSE_NPZ="$DENSE_NPZ" python3 scripts/gap_csim_ps_dense_accuracy.py
N_GAP_COMPARE=100 python3 scripts/gap_csim_keras_align.py

python3 - <<'PY'
import json
d = json.load(open('results/gap_csim_ps_dense_accuracy.json'))
k = json.load(open('results/gap_csim_keras_align.json'))
top1 = d['csim_ps_dense_top1_pct']
mae = k['summary']['csim_vs_keras_mae_mean']
print('GATE1: Top1=%.1f%% MAE=%.4f' % (top1, mae))
ok = top1 >= 75 and mae <= 0.35
print('PASS' if ok else 'FAIL')
raise SystemExit(0 if ok else 1)
PY
