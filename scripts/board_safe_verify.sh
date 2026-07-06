#!/bin/bash
# Safe board verification: no N=100 benchmark, no board_s2mm_scan.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"
mkdir -p results

source ~/miniconda3/etc/profile.d/conda.sh
conda activate edgeai_39

BOARD_IP="${BOARD_IP:-192.168.1.40}"
BOARD_USER="${BOARD_USER:-root}"
BOARD_PASS="${BOARD_PASS:-root}"

echo "[$(date '+%F %T')] === board_safe_verify @ ${BOARD_USER}@${BOARD_IP} ==="

sshpass -p "$BOARD_PASS" ssh -o StrictHostKeyChecking=no "${BOARD_USER}@${BOARD_IP}" \
  "mkdir -p /tmp/edgeai_bench"

SCP_FILES=(
  "$REPO/scripts/dma_infer_common.py"
  "$REPO/scripts/slot32_layout.py"
  "$REPO/scripts/board_fetch_gap.py"
  "$REPO/scripts/board_load_only.sh"
  /scripts/board_fix_hp0_width.py
  "$REPO/deploy/cifar10_accel.bit"
  "$REPO/deploy/cifar10_bench.npz"
)
if [ -f "$REPO/deploy/dense_head.npz" ]; then
  SCP_FILES+=("$REPO/deploy/dense_head.npz")
fi

sshpass -p "$BOARD_PASS" scp -o StrictHostKeyChecking=no \
  "${SCP_FILES[@]}" \
  "${BOARD_USER}@${BOARD_IP}:/tmp/edgeai_bench/"

echo "--- PL reload (FORCE_PL_RELOAD=1) ---"
sshpass -p "$BOARD_PASS" ssh -o StrictHostKeyChecking=no "${BOARD_USER}@${BOARD_IP}" \
  "cp /tmp/edgeai_bench/cifar10_accel.bit /lib/firmware/cifar10_accel.bit && \
   chmod +x /tmp/edgeai_bench/board_load_only.sh && \
  /scripts/board_fix_hp0_width.py
   FORCE_PL_RELOAD=1 sh /tmp/edgeai_bench/board_load_only.sh"
  /scripts/board_fix_hp0_width.py

BOARD_ENV="OUT_DIM=24 OUT_BYTES=96 OUT_LAYOUT=gap_ps OUT_FIXED_SCALE=1024 OUTPUT_PACK_MODE=serial BOARD_S2MM_SLOT_TIMING=0 SAMPLE_IDX=0"

echo "--- board_fetch_gap sample 0 ---"
FETCH_LOG="results/board_safe_fetch.json"
sshpass -p "$BOARD_PASS" ssh -o StrictHostKeyChecking=no "${BOARD_USER}@${BOARD_IP}" \
  "cd /tmp/edgeai_bench && ${BOARD_ENV} python3 -u board_fetch_gap.py" \
  | tee "$FETCH_LOG"

CSIM_BEATS="$REPO/notebooks/hls4ml_prj/tb_data/csim_axis_beats.log"
if [ ! -f "$CSIM_BEATS" ]; then
  echo "ERROR: missing $CSIM_BEATS" >&2
  exit 1
fi

python3 - "$REPO" "$FETCH_LOG" "$CSIM_BEATS" <<'PY'
import json
import struct
import sys
from pathlib import Path

repo = Path(sys.argv[1])
fetch_path = Path(sys.argv[2])
beats_path = Path(sys.argv[3])
lines = fetch_path.read_text(encoding="utf-8").strip().splitlines()
board = json.loads(lines[-1])
raw = bytes.fromhex(board["raw_hex"])
out_dim = int(board.get("out_dim", 24))
board_words = [struct.unpack_from("<I", raw, w * 4)[0] for w in range(out_dim)]
csim_words = [int(x, 16) for x in beats_path.read_text(encoding="utf-8").splitlines()[0].split()]
n = min(len(board_words), len(csim_words), out_dim)
match_count = sum(1 for i in range(n) if board_words[i] == csim_words[i])
dma_src = (repo / "scripts" / "dma_infer_common.py").read_text(encoding="utf-8")
rcu_safe = "_page_maps" in dma_src and "_map_page" in dma_src
print("match_count=%d/%d" % (match_count, n))
print("board_words[0:8]=", board_words[:8])
print("csim_words[0:8]=", csim_words[:8])
print("dma_ok=%s status=%s" % (board.get("ok"), board.get("status")))
print("rcu_safe_devmem_deployed=%s" % rcu_safe)
PY

if [ "${FULL_BENCH:-0}" = "1" ]; then
  echo "--- optional FULL_BENCH: N_ACCURACY=10 ---"
  sshpass -p "$BOARD_PASS" scp -o StrictHostKeyChecking=no \
    "$REPO/scripts/board_benchmark.py" \
    "${BOARD_USER}@${BOARD_IP}:/tmp/edgeai_bench/"
  sshpass -p "$BOARD_PASS" ssh -o StrictHostKeyChecking=no "${BOARD_USER}@${BOARD_IP}" \
    "cd /tmp/edgeai_bench && ${BOARD_ENV} DENSE_NPZ=dense_head.npz N_ACCURACY=10 python3 -u board_benchmark.py" \
    | tee results/board_safe_bench.log
fi

echo "=== board_safe_verify done ==="
