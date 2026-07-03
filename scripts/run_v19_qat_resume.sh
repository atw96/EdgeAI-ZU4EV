#!/bin/bash
# Route 1: Input QActivation QAT fine-tune -> bit_exact convert -> csim Top-1 gate.
# Plan B manual PREC patches DISABLED (v17/profiling/conv1ab/plan_b_extras).
set -euo pipefail

REPO="/home/atw/Edge_AI_Acc/claude/EdgeAI-ZU4EV_Claude"
LOG="${REPO}/results/v19_qat_pipeline.log"
HLS="${REPO}/notebooks/hls4ml_prj"

FT_EPOCHS="${FT_EPOCHS:-40}"
CSIM_TOP1_MIN="${CSIM_TOP1_MIN:-75}"
CSIM_MAE_MAX="${CSIM_MAE_MAX:-0.35}"
MAE_HARD_FAIL="${MAE_HARD_FAIL:-0}"
N_ACCURACY="${N_ACCURACY:-100}"
SKIP_FINETUNE="${SKIP_FINETUNE:-0}"

exec >> "$LOG" 2>&1
log() { echo "[$(date '+%F %T')] [route1] $*"; }

track() {
  V19_STEP="$1" V19_STATUS="$2" V19_MESSAGE="$3" \
    python3 "${REPO}/scripts/v19_tracker.py" || true
}

source ~/miniconda3/etc/profile.d/conda.sh
cd "$REPO"

export OUTPUT_AXIS_BITS=32 OUTPUT_PACK_MODE=slot AXI_DATAFLOW=0
export OUT_DIM=24 OUT_BYTES=92 OUT_LAYOUT=gap_ps OUT_FIXED_SCALE=256
export GAP_ONLY=1
export PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python

log "=== v19 Route 1: input_qact QAT -> bit_exact -> Top-1 gate ==="
log "Plan B PREC patches DISABLED | TOP1>=${CSIM_TOP1_MIN}% MAE auxiliary=${CSIM_MAE_MAX}"
track "route1" "start" "input_qact finetune + bit_exact"

# ── 1) QAT fine-tune with Input QActivation (edgeai_39 / TF2.6 + QKeras) ──
conda activate edgeai_39
bash scripts/ensure_edgeai39_protobuf.sh
if [[ "$SKIP_FINETUNE" == "1" ]]; then
  log "SKIP_FINETUNE=1 — skip input_qact fine-tune"
else
  FT_EPOCHS="$FT_EPOCHS" python3 scripts/v19_qat_input_qact_finetune.py
fi
python3 scripts/verify_q6_bench_accuracy.py
python3 scripts/patch_gap_only.py

# ── 2) Notebook Route 1 (bit_exact, no manual PREC) ──
python3 scripts/patch_notebook_bitexact_route1.py

# ── 3) bit_exact convert (edgeai_hls4ml13 / hls4ml 1.3) ──
conda activate edgeai_hls4ml13
export BAK_TAG="route1_$(date +%Y%m%d_%H%M%S)"
python3 scripts/v19_bitexact_convert.py
grep -E 'input_t|result_t|conv1a' "${HLS}/firmware/defines.h" | head -8 || true

# ── 4) HLS patches + csim (edgeai_39 for Vivado csim) ──
conda activate edgeai_39
bash scripts/ensure_edgeai39_protobuf.sh
python3 scripts/patch_hls_rf_v14.py
python3 scripts/patch_hls_restore_dataflow.py
python3 scripts/patch_hls_conv_stream.py || true
python3 scripts/patch_hls_conv_cyclic_restore.py || true
python3 scripts/patch_hls_stream_depth.py
python3 scripts/patch_hls_dense_mult.py
python3 scripts/patch_hls_dense_antihang.py
python3 scripts/patch_hls_dense_resource_antihang.py
python3 scripts/patch_hls_mult_strategy.py
python3 scripts/patch_hls_axi_top.py || true
python3 scripts/patch_axi_wrapper.py
python3 scripts/patch_axi_testbench.py
python3 scripts/patch_hls_axi_csim_tb.py || true

export SKIP_BOARD="${SKIP_BOARD:-1}"
N_GAP_COMPARE="$N_ACCURACY" N_ACCURACY="$N_ACCURACY" bash scripts/run_gap_axi_csim.sh \
  2>&1 | tee "${REPO}/results/gap_axi_csim_v19_route1.log"

python3 scripts/csim_zero_gate.py || {
  track "route1" "fail" "csim all-zero"
  exit 1
}

N_GAP_COMPARE="$N_ACCURACY" python3 scripts/gap_csim_keras_align.py
N_ACCURACY="$N_ACCURACY" OUT_DIM=24 python3 scripts/gap_csim_ps_dense_accuracy.py \
  --min-top1 "$CSIM_TOP1_MIN" || true

MAE_HARD_FAIL="$MAE_HARD_FAIL" CSIM_TOP1_MIN="$CSIM_TOP1_MIN" CSIM_MAE_MAX="$CSIM_MAE_MAX" \
  python3 scripts/v19_csim_route1_gates.py --min-top1 "$CSIM_TOP1_MIN" --max-mae "$CSIM_MAE_MAX" || {
  MAE_VAL=$(python3 -c "import json; print(json.load(open('results/gap_csim_keras_align.json'))['summary']['csim_vs_keras_mae_mean'])" 2>/dev/null || echo nan)
  TOP1_VAL=$(python3 -c "import json; print(json.load(open('results/gap_csim_ps_dense_accuracy.json'))['csim_ps_dense_top1_pct'])" 2>/dev/null || echo nan)
  log "Route 1 gates FAIL: MAE=$MAE_VAL Top1=$TOP1_VAL%"
  track "route1" "fail" "MAE=$MAE_VAL Top1=$TOP1_VAL%"
  exit 1
}

MAE_VAL=$(python3 -c "import json; print(json.load(open('results/gap_csim_keras_align.json'))['summary']['csim_vs_keras_mae_mean'])")
TOP1_VAL=$(python3 -c "import json; print(json.load(open('results/gap_csim_ps_dense_accuracy.json'))['csim_ps_dense_top1_pct'])")
log "Route 1 gates PASS: MAE=$MAE_VAL (aux) Top1=$TOP1_VAL%"
track "route1" "ok" "MAE=$MAE_VAL Top1=$TOP1_VAL%"

log "=== v19 Route 1 PASS — next: bash scripts/run_v19_bit_board.sh ==="
