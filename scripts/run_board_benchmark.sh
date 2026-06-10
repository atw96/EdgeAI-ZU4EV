#!/bin/bash
# Deploy FPGA benchmark to board and collect results.
set -euo pipefail

BOARD_IP="${BOARD_IP:-192.168.1.40}"
BOARD_USER="${BOARD_USER:-root}"
BOARD_PASS="${BOARD_PASS:-root}"
REPO="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== Board FPGA benchmark @ ${BOARD_USER}@${BOARD_IP} ==="

sshpass -p "$BOARD_PASS" ssh -o StrictHostKeyChecking=no "${BOARD_USER}@${BOARD_IP}" \
  "mkdir -p /tmp/edgeai_bench"

sshpass -p "$BOARD_PASS" scp -o StrictHostKeyChecking=no \
  "$REPO/scripts/board_benchmark.py" \
  "$REPO/scripts/board_load_only.sh" \
  "$REPO/deploy/cifar10_bench.npz" \
  "$REPO/deploy/cifar10_accel.bit" \
  "${BOARD_USER}@${BOARD_IP}:/tmp/edgeai_bench/"

sshpass -p "$BOARD_PASS" ssh -o StrictHostKeyChecking=no "${BOARD_USER}@${BOARD_IP}" \
  "cp /tmp/edgeai_bench/cifar10_accel.bit /lib/firmware/cifar10_accel.bit && \
   chmod +x /tmp/edgeai_bench/board_load_only.sh && \
   FORCE_PL_RELOAD=1 sh /tmp/edgeai_bench/board_load_only.sh"

sshpass -p "$BOARD_PASS" ssh -o StrictHostKeyChecking=no "${BOARD_USER}@${BOARD_IP}" \
  "cd /tmp/edgeai_bench && python3 board_benchmark.py"

sshpass -p "$BOARD_PASS" scp -o StrictHostKeyChecking=no \
  "${BOARD_USER}@${BOARD_IP}:/tmp/edgeai_bench/fpga_benchmark.json" \
  "$REPO/results/fpga_benchmark.json"

echo "Saved: $REPO/results/fpga_benchmark.json"
