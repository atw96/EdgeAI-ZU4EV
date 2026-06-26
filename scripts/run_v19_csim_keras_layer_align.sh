#!/bin/bash
# Deep csim vs Keras layer alignment (BN fusion mapping + GAP tri-compare)
set -euo pipefail

REPO="/home/atw/Edge_AI_Acc/claude/EdgeAI-ZU4EV_Claude"
LOG="${REPO}/results/v19_csim_keras_layer_align.log"
N_ALIGN="${N_ALIGN:-20}"

exec > >(tee -a "$LOG") 2>&1
log() { echo "[$(date '+%F %T')] $*"; }

source ~/miniconda3/etc/profile.d/conda.sh
conda activate edgeai_hls4ml13
cd "$REPO"

log "=== csim/Keras layer alignment N=$N_ALIGN ==="
N_ALIGN="$N_ALIGN" python3 scripts/v19_csim_keras_layer_align.py

log "=== DONE ==="
python3 -m json.tool results/v19_csim_keras_layer_align.json | head -60
