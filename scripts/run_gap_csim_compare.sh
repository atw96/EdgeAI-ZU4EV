#!/bin/bash
# Deploy board_fetch_gap.py, run HLS csim vs board GAP comparison.
set -euo pipefail

REPO="/home/atw/Edge_AI_Acc/claude/EdgeAI-ZU4EV_Claude"
BOARD_IP="${BOARD_IP:-192.168.1.40}"
BOARD_PASS="${BOARD_PASS:-root}"
LOG="${REPO}/results/gap_csim_compare.log"

exec > >(tee -a "$LOG") 2>&1
log() { echo "[$(date '+%F %T')] $*"; }

source ~/miniconda3/etc/profile.d/conda.sh
conda activate edgeai_39
cd "$REPO"

log "=== Deploy gap fetch scripts to board ==="
sshpass -p "$BOARD_PASS" scp -o StrictHostKeyChecking=no \
  scripts/board_fetch_gap.py \
  scripts/dma_infer_common.py \
  scripts/slot32_layout.py \
  deploy/cifar10_bench.npz \
  "root@${BOARD_IP}:/tmp/edgeai_bench/"

log "=== gap_csim_board_compare.py ==="
N_GAP_COMPARE="${N_GAP_COMPARE:-10}" BOARD_IP="$BOARD_IP" BOARD_PASS="$BOARD_PASS" \
  python3 scripts/gap_csim_board_compare.py

log "=== DONE ==="
