#!/usr/bin/env bash
set -euo pipefail

REPO_WSL="/home/atw/Edge_AI_Acc/claude/EdgeAI-ZU4EV_Claude"
BOARD="${BOARD_IP:-192.168.0.100}"
SSH_OPTS=(-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=15 -o HostKeyAlgorithms=+ssh-rsa)

cd "$REPO_WSL"

echo "[STEP 2] SCP deploy artifacts -> root@${BOARD}:/root/"
sshpass -p root scp "${SSH_OPTS[@]}" \
  deploy/model_int8.tflite \
  deploy/cifar10_bench.npz \
  scripts/cpu_baseline.py \
  "root@${BOARD}:/root/"

echo "[STEP 3] Check tflite_runtime on board"
if sshpass -p root ssh "${SSH_OPTS[@]}" "root@${BOARD}" \
  'python3 -c "import tflite_runtime; print(\"tflite_runtime OK\")"' 2>/dev/null; then
  echo "[STEP 4] PLAN A: cpu_baseline.py"
  sshpass -p root ssh "${SSH_OPTS[@]}" "root@${BOARD}" \
    'cd /root && mkdir -p results && python3 cpu_baseline.py'
else
  echo "[STEP 4] tflite_runtime missing — run scripts/board_install_tflite_and_rerun.sh first"
  exit 1
fi

echo "[STEP 5] Fetch results/cpu_baseline.json"
mkdir -p results
sshpass -p root scp "${SSH_OPTS[@]}" \
  "root@${BOARD}:/root/results/cpu_baseline.json" \
  results/cpu_baseline.json

echo "[DONE] Local results:"
cat results/cpu_baseline.json
