#!/bin/bash
# P0-2: official hls4ml layer trace + log to v19 tracker.
set -euo pipefail
REPO="/home/atw/Edge_AI_Acc/claude/EdgeAI-ZU4EV_Claude"
LOG="${REPO}/results/v19_p0_layer_trace.log"
exec > >(tee -a "$LOG") 2>&1
log() { echo "[$(date '+%F %T')] $*"; }

source ~/miniconda3/etc/profile.d/conda.sh
conda activate edgeai_hls4ml13
cd "$REPO"

log "=== P0-2: hls4ml official layer trace ==="
N_TRACE="${N_TRACE:-10}" python3 scripts/v19_p0_layer_trace.py

V19_STEP="p0-2" V19_STATUS="ok" V19_MESSAGE="layer trace written results/v19_p0_layer_trace.json" \
  python3 scripts/v19_tracker.py || true

log "=== P0-2 DONE ==="
