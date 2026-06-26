#!/bin/bash
set -euo pipefail
BOARD_IP="${BOARD_IP:-192.168.1.40}"
REPO="/home/atw/Edge_AI_Acc/claude/EdgeAI-ZU4EV_Claude"
sshpass -p "${BOARD_PASS:-root}" scp -o StrictHostKeyChecking=no \
  "$REPO/scripts/board_s2mm_scan.py" "root@${BOARD_IP}:/tmp/edgeai_bench/"
for L in 20 24 32 40; do
  echo "=== S2MM_LEN=$L ==="
  sshpass -p "${BOARD_PASS:-root}" ssh -o StrictHostKeyChecking=no "root@${BOARD_IP}" \
    "cd /tmp/edgeai_bench && S2MM_LEN_OVERRIDE=$L OUT_SCAN_BYTES=64 python3 -u board_s2mm_scan.py" | head -5
done
