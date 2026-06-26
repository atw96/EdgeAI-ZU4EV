#!/bin/bash
# Deploy gap_ps scripts + dense weights, run board_infer + benchmark.
set -euo pipefail

REPO="/home/atw/Edge_AI_Acc/claude/EdgeAI-ZU4EV_Claude"
BOARD_IP="${BOARD_IP:-192.168.1.40}"
BOARD_PASS="${BOARD_PASS:-root}"
LOG="${REPO}/results/gap_ps_board_eval.log"

ENV="OUT_DIM=24 OUT_BYTES=92 OUT_LAYOUT=gap_ps OUT_FIXED_SCALE=256"

exec > >(tee -a "$LOG") 2>&1
log() { echo "[$(date '+%F %T')] $*"; }

log "=== gap_ps board eval (infer + benchmark) ==="
cd "$REPO"

sshpass -p "$BOARD_PASS" ssh -o StrictHostKeyChecking=no "root@${BOARD_IP}" \
  "mkdir -p /tmp/edgeai_bench"

sshpass -p "$BOARD_PASS" scp -o StrictHostKeyChecking=no \
  scripts/board_infer.py \
  scripts/board_benchmark.py \
  scripts/board_diagnose.py \
  scripts/dma_infer_common.py \
  scripts/slot32_layout.py \
  deploy/cifar10_bench.npz \
  deploy/dense_head.npz \
  "root@${BOARD_IP}:/tmp/edgeai_bench/"

log "--- board_infer.py ---"
sshpass -p "$BOARD_PASS" ssh -o StrictHostKeyChecking=no "root@${BOARD_IP}" \
  "cd /tmp/edgeai_bench && ${ENV} python3 -u board_infer.py" || true

log "--- board_diagnose.py ---"
sshpass -p "$BOARD_PASS" ssh -o StrictHostKeyChecking=no "root@${BOARD_IP}" \
  "cd /tmp/edgeai_bench && ${ENV} python3 -u board_diagnose.py"

log "--- board_benchmark.py (100 images) ---"
sshpass -p "$BOARD_PASS" ssh -o StrictHostKeyChecking=no "root@${BOARD_IP}" \
  "cd /tmp/edgeai_bench && ${ENV} N_BENCH=100 N_ACCURACY=100 python3 -u board_benchmark.py"

sshpass -p "$BOARD_PASS" scp -o StrictHostKeyChecking=no \
  "root@${BOARD_IP}:/tmp/edgeai_bench/fpga_benchmark.json" \
  "$REPO/results/fpga_benchmark_gap_ps.json"

log "=== gap_ps board eval DONE ==="
