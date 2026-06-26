#!/bin/bash
set -euo pipefail
BOARD_IP="${BOARD_IP:-192.168.1.40}"
BOARD_USER="${BOARD_USER:-root}"
BOARD_PASS="${BOARD_PASS:-root}"
REPO="$(cd "$(dirname "$0")/.." && pwd)"

sshpass -p "$BOARD_PASS" scp -o StrictHostKeyChecking=no \
  "$REPO/scripts/board_diagnose.py" \
  "$REPO/scripts/dma_infer_common.py" \
  "$REPO/deploy/cifar10_bench.npz" \
  "${BOARD_USER}@${BOARD_IP}:/tmp/edgeai_bench/"

sshpass -p "$BOARD_PASS" ssh -o StrictHostKeyChecking=no "${BOARD_USER}@${BOARD_IP}" \
  "cd /tmp/edgeai_bench && python3 -u board_diagnose.py"
