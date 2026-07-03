#!/bin/bash
# Phase C: layer_align + Top-1 gates (+ optional board if pass)
set -euo pipefail

REPO="/home/atw/Edge_AI_Acc/claude/EdgeAI-ZU4EV_Claude"
CSIM_TOP1_MIN="${CSIM_TOP1_MIN:-75}"
CSIM_MAE_MAX="${CSIM_MAE_MAX:-0.35}"
MAE_HARD_FAIL="${MAE_HARD_FAIL:-0}"
N_ALIGN="${N_ALIGN:-20}"
SKIP_BOARD="${SKIP_BOARD:-1}"

source ~/miniconda3/etc/profile.d/conda.sh
cd "$REPO"
export PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python
export OUT_DIM=24 OUT_BYTES=92 OUT_LAYOUT=gap_ps OUT_FIXED_SCALE=256 GAP_ONLY=1

log() { echo "[$(date '+%F %T')] [phase-c] $*"; }

log "=== Phase C gates Top-1>=${CSIM_TOP1_MIN}% ==="

conda activate edgeai_hls4ml13
python3 scripts/v19_bitexact_probe.py

conda activate edgeai_39
bash scripts/ensure_edgeai39_protobuf.sh
N_ALIGN="$N_ALIGN" bash scripts/run_v19_csim_keras_layer_align.sh

N_ACCURACY="${N_ACCURACY:-100}" python3 scripts/gap_csim_ps_dense_accuracy.py --min-top1 "$CSIM_TOP1_MIN" || true

MAE_HARD_FAIL="$MAE_HARD_FAIL" CSIM_TOP1_MIN="$CSIM_TOP1_MIN" CSIM_MAE_MAX="$CSIM_MAE_MAX" \
  python3 scripts/v19_csim_route1_gates.py --min-top1 "$CSIM_TOP1_MIN" --max-mae "$CSIM_MAE_MAX"

TOP1_VAL=$(python3 -c "import json; print(json.load(open('results/gap_csim_ps_dense_accuracy.json'))['csim_ps_dense_top1_pct'])")
PASS=$(python3 -c "import json; print(json.load(open('results/v19_route1_gates.json'))['overall_pass'])")
log "Top-1=${TOP1_VAL}% overall_pass=${PASS}"

if [[ "$PASS" == "True" ]] && [[ "$SKIP_BOARD" == "0" ]]; then
  log "Top-1 pass — fixing known_hosts and running board"
  ssh-keygen -f ~/.ssh/known_hosts -R 192.168.1.40 2>/dev/null || true
  SKIP_BOARD=0 bash scripts/run_v19_bit_board.sh
fi

log "=== Phase C DONE ==="
cat results/v19_route1_gates.json
