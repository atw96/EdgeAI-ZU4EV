#!/bin/bash
set -euo pipefail

REPO="/home/atw/Edge_AI_Acc/claude/EdgeAI-ZU4EV_Claude"
cd "$REPO"
mkdir -p results

BOARD_IP="${BOARD_IP:-192.168.1.40}"
BOARD_PASS="${BOARD_PASS:-root}"
BOARD_DIR="/tmp/edgeai_bench"
SERIAL_ENV="OUT_DIM=24 OUT_BYTES=96 OUT_LAYOUT=gap_ps OUT_FIXED_SCALE=1024 OUTPUT_PACK_MODE=serial BOARD_S2MM_SLOT_TIMING=0"

ssh_board() {
  sshpass -p "$BOARD_PASS" ssh -o ConnectTimeout=8 -o StrictHostKeyChecking=no \
    -o UserKnownHostsFile=/dev/null "root@${BOARD_IP}" "$@"
}

scp_board() {
  sshpass -p "$BOARD_PASS" scp -o ConnectTimeout=8 -o StrictHostKeyChecking=no \
    -o UserKnownHostsFile=/dev/null "$@"
}

echo "[$(date '+%F %T')] === DMA64 board verify @ ${BOARD_IP} ==="
ssh_board "mkdir -p ${BOARD_DIR}"

scp_board \
  deploy/cifar10_accel.bit \
  deploy/cifar10_bench.npz \
  deploy/dense_head.npz \
  scripts/dma_infer_common.py \
  scripts/slot32_layout.py \
  scripts/board_load_only.sh \
  scripts/board_aa_serial96_diag.py \
  scripts/board_fetch_gap.py \
  scripts/board_benchmark.py \
  "root@${BOARD_IP}:${BOARD_DIR}/"

echo "--- PL reload ---"
ssh_board "cp ${BOARD_DIR}/cifar10_accel.bit /lib/firmware/ && chmod +x ${BOARD_DIR}/board_load_only.sh && FORCE_PL_RELOAD=1 sh ${BOARD_DIR}/board_load_only.sh"

STATE=$(ssh_board "cat /sys/class/fpga_manager/fpga0/state")
echo "fpga state: ${STATE}"
if [[ "$STATE" != "operating" ]]; then
  echo "ERROR: PL not operating"
  exit 1
fi

echo "--- 0xAA serial96 diag ---"
ssh_board "cd ${BOARD_DIR} && ${SERIAL_ENV} BENCH_NPZ=${BOARD_DIR}/cifar10_bench.npz timeout 45 python3 -u board_aa_serial96_diag.py" \
  | tee results/board_dma64_aa_diag.log

echo "--- board_fetch_gap sample 0 ---"
ssh_board "cd ${BOARD_DIR} && ${SERIAL_ENV} SAMPLE_IDX=0 timeout 45 python3 -u board_fetch_gap.py" \
  | tee results/board_dma64_fetch.json

CSIM_BEATS="${REPO}/notebooks/hls4ml_prj/tb_data/csim_axis_beats.log"
python3 - "$REPO" results/board_dma64_fetch.json "$CSIM_BEATS" <<'PY'
import json, struct, sys
from pathlib import Path
fetch_path = Path(sys.argv[2])
lines = fetch_path.read_text(encoding="utf-8").strip().splitlines()
board = json.loads(lines[-1])
raw = bytes.fromhex(board["raw_hex"])
out_dim = int(board.get("out_dim", 24))
board_words = [struct.unpack_from("<I", raw, w * 4)[0] for w in range(out_dim)]
csim_words = [int(x, 16) for x in Path(sys.argv[3]).read_text(encoding="utf-8").splitlines()[0].split()]
n = min(len(board_words), len(csim_words), out_dim)
match_count = sum(1 for i in range(n) if board_words[i] == csim_words[i])
print("match_count=%d/%d" % (match_count, n))
print("board_words[0:8]=", board_words[:8])
print("csim_words[0:8]=", csim_words[:8])
if match_count < n:
    raise SystemExit(1)
PY

echo "--- N=10 benchmark ---"
ssh_board "cd ${BOARD_DIR} && ${SERIAL_ENV} DENSE_NPZ=${BOARD_DIR}/dense_head.npz N_ACCURACY=10 timeout 120 python3 -u board_benchmark.py" \
  | tee results/board_dma64_bench_n10.log

echo "--- N=100 benchmark ---"
ssh_board "cd ${BOARD_DIR} && ${SERIAL_ENV} DENSE_NPZ=${BOARD_DIR}/dense_head.npz N_ACCURACY=100 timeout 300 python3 -u board_benchmark.py" \
  | tee results/board_dma64_bench_n100.log

echo "=== DMA64 board verify done ==="
