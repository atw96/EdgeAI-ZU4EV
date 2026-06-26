#!/bin/bash
# Deploy fixed scripts + run serial32 benchmark (no bit rebuild).
set -euo pipefail

BOARD_IP="${BOARD_IP:-192.168.1.40}"
BOARD_PASS="${BOARD_PASS:-root}"
REPO="$(cd "$(dirname "$0")/.." && pwd)"
LOG="${REPO}/results/serial32_board_bench.log"

exec > >(tee -a "$LOG") 2>&1
echo "[$(date '+%F %T')] === serial32 board bench (warm-up fix) ==="

sshpass -p "$BOARD_PASS" scp -o StrictHostKeyChecking=no \
  "$REPO/scripts/board_infer.py" \
  "$REPO/scripts/board_benchmark.py" \
  "$REPO/scripts/dma_infer_common.py" \
  "root@${BOARD_IP}:/tmp/edgeai_bench/"

ENV="OUT_BYTES=40 OUT_LAYOUT=serial32 OUT_FIXED_SCALE=256"

sshpass -p "$BOARD_PASS" ssh -o StrictHostKeyChecking=no "root@${BOARD_IP}" \
  "cd /tmp/edgeai_bench && ${ENV} python3 -u board_infer.py" || true

sshpass -p "$BOARD_PASS" ssh -o StrictHostKeyChecking=no "root@${BOARD_IP}" \
  "cd /tmp/edgeai_bench && ${ENV} N_BENCH=100 N_ACCURACY=100 python3 -u board_benchmark.py"

sshpass -p "$BOARD_PASS" scp -o StrictHostKeyChecking=no \
  "root@${BOARD_IP}:/tmp/edgeai_bench/fpga_benchmark.json" \
  "$REPO/results/fpga_benchmark.json"

echo "[$(date '+%F %T')] === done ==="
