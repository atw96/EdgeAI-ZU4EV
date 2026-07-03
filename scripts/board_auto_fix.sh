#!/bin/bash
# Deploy inference scripts, reload PL, run clean inference + benchmark.
# IMPORTANT: Never run board_dma_verify.py before inference — short DMA
# transfers pollute the HLS input stream.
set -euo pipefail

BOARD_IP="${BOARD_IP:-192.168.1.40}"
BOARD_USER="${BOARD_USER:-root}"
BOARD_PASS="${BOARD_PASS:-root}"
REPO="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== EdgeAI clean deploy @ ${BOARD_USER}@${BOARD_IP} ==="

sshpass -p "$BOARD_PASS" ssh -o StrictHostKeyChecking=no "${BOARD_USER}@${BOARD_IP}" \
  "mkdir -p /tmp/edgeai_bench"

OUT_SCALE="${OUT_FIXED_SCALE:-1024}"
OUT_BYTES="${OUT_BYTES:-20}"
OUT_LAYOUT="${OUT_LAYOUT:-int16}"
OUT_DIM="${OUT_DIM:-10}"
OUTPUT_PACK_MODE="${OUTPUT_PACK_MODE:-slot}"
BOARD_ENV="OUT_FIXED_SCALE=${OUT_SCALE} OUT_BYTES=${OUT_BYTES} OUT_LAYOUT=${OUT_LAYOUT} OUT_DIM=${OUT_DIM} OUTPUT_PACK_MODE=${OUTPUT_PACK_MODE} DENSE_NPZ=dense_head.npz"
sshpass -p "$BOARD_PASS" scp -o StrictHostKeyChecking=no \
  "$REPO/scripts/board_infer.py" \
  "$REPO/scripts/board_benchmark.py" \
  "$REPO/scripts/board_diagnose.py" \
  "$REPO/scripts/board_dma_verify.py" \
  "$REPO/scripts/board_load_only.sh" \
  "$REPO/scripts/dma_infer_common.py" \
  "$REPO/scripts/slot32_layout.py" \
  "$REPO/scripts/board_fetch_gap.py" \
  "$REPO/deploy/cifar10_bench.npz" \
  "$REPO/deploy/cifar10_accel.bit" \
  "${BOARD_USER}@${BOARD_IP}:/tmp/edgeai_bench/"
if [ -f "$REPO/deploy/dense_head.npz" ]; then
  sshpass -p "$BOARD_PASS" scp -o StrictHostKeyChecking=no \
    "$REPO/deploy/dense_head.npz" \
    "${BOARD_USER}@${BOARD_IP}:/tmp/edgeai_bench/"
fi

echo "--- Reload PL (clears HLS pipeline) ---"
sshpass -p "$BOARD_PASS" ssh -o StrictHostKeyChecking=no "${BOARD_USER}@${BOARD_IP}" \
  "cp /tmp/edgeai_bench/cifar10_accel.bit /lib/firmware/cifar10_accel.bit && \
   chmod +x /tmp/edgeai_bench/board_load_only.sh && \
   FORCE_PL_RELOAD=1 sh /tmp/edgeai_bench/board_load_only.sh"

echo "--- Inference smoke (board_infer.py, ${BOARD_ENV}) ---"
sshpass -p "$BOARD_PASS" ssh -o StrictHostKeyChecking=no "${BOARD_USER}@${BOARD_IP}" \
  "cd /tmp/edgeai_bench && ${BOARD_ENV} python3 -u board_infer.py" || true
INFER_RC=$?

echo "--- Full benchmark (100 images) ---"
sshpass -p "$BOARD_PASS" ssh -o StrictHostKeyChecking=no "${BOARD_USER}@${BOARD_IP}" \
  "cd /tmp/edgeai_bench && ${BOARD_ENV} N_BENCH=100 N_ACCURACY=100 python3 -u board_benchmark.py"

sshpass -p "$BOARD_PASS" scp -o StrictHostKeyChecking=no \
  "${BOARD_USER}@${BOARD_IP}:/tmp/edgeai_bench/fpga_benchmark.json" \
  "$REPO/results/fpga_benchmark.json"

echo "--- Optional: register-only DMA check (safe, no stream xfer) ---"
sshpass -p "$BOARD_PASS" ssh -o StrictHostKeyChecking=no "${BOARD_USER}@${BOARD_IP}" \
  "python3 -u /tmp/edgeai_bench/board_dma_verify.py" || true

echo "=== Done. infer_rc=$INFER_RC ==="
exit "$INFER_RC"
