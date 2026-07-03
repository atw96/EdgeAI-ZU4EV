#!/bin/bash
# ILA session: trigger inference WITHOUT fpga_manager PL reload (keeps JTAG debug hub).
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"

BOARD_IP="${BOARD_IP:-192.168.1.40}"
BOARD_USER="${BOARD_USER:-root}"
BOARD_PASS="${BOARD_PASS:-root}"

echo "[$(date '+%F %T')] === board_ila_fetch (NO PL reload) ==="
echo "WARN: Do NOT run board_load_only / board_safe_verify while ILA is armed."

sshpass -p "$BOARD_PASS" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  "${BOARD_USER}@${BOARD_IP}" "mkdir -p /tmp/edgeai_bench"

sshpass -p "$BOARD_PASS" scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  "$REPO/scripts/board_fetch_gap.py" \
  "$REPO/scripts/board_dma_quick_diag.py" \
  "$REPO/scripts/dma_infer_common.py" \
  "$REPO/scripts/slot32_layout.py" \
  "$REPO/deploy/cifar10_bench.npz" \
  "${BOARD_USER}@${BOARD_IP}:/tmp/edgeai_bench/"

BOARD_ENV="OUT_DIM=24 OUT_BYTES=96 OUT_LAYOUT=gap_ps OUT_FIXED_SCALE=1024 OUTPUT_PACK_MODE=serial SAMPLE_IDX=0"

echo "--- fpga state (expect operating; JTAG program does not update this sysfs) ---"
sshpass -p "$BOARD_PASS" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  "${BOARD_USER}@${BOARD_IP}" "cat /sys/class/fpga_manager/fpga0/state"

if [ "${DMA_DIAG:-0}" = "1" ]; then
  echo "--- board_dma_quick_diag ---"
  sshpass -p "$BOARD_PASS" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    "${BOARD_USER}@${BOARD_IP}" \
    "cd /tmp/edgeai_bench && DMA_IOC_TIMEOUT_S=8 ${BOARD_ENV} python3 -u board_dma_quick_diag.py"
fi

echo "--- board_fetch_gap sample 0 ---"
sshpass -p "$BOARD_PASS" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  "${BOARD_USER}@${BOARD_IP}" \
  "cd /tmp/edgeai_bench && ${BOARD_ENV} python3 -u board_fetch_gap.py" \
  | tee results/board_ila_fetch.json

echo "=== board_ila_fetch done ==="
