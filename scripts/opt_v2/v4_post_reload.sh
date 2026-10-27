#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
# 200 frames after this morning's PL reload. HP0 is already 64-bit. One SSH.
set -euo pipefail
REPO=${EDGEAI_ROOT}
IP=${BOARD_IP:?BOARD_IP}
export SSHPASS="${SSHPASS:?SSHPASS}"
OPTS="-o ConnectTimeout=8 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ServerAliveInterval=15"
echo "[$(date '+%F %T')] post-reload 200"
STATE=$(timeout 20 sshpass -e ssh $OPTS root@$IP 'cat /sys/class/fpga_manager/fpga0/state')
echo "state [$STATE]"
if [ "$STATE" != "operating" ]; then
  echo "refuse DMA"
  exit 2
fi
timeout 60 sshpass -e scp $OPTS "$REPO/results/opt_v2/bench10k_packed.npz" root@$IP:/tmp/edgeai_bench/bench10k_packed.npz
timeout 120 sshpass -e ssh $OPTS root@$IP 'cd /tmp/edgeai_bench && export OUT_DIM=24 OUT_BYTES=96 OUT_LAYOUT=gap_ps OUT_FIXED_SCALE=1024 OUTPUT_PACK_MODE=serial DENSE_NPZ=/tmp/edgeai_bench/dense_head.npz DMA_IOC_TIMEOUT_S=5 PYTHONUNBUFFERED=1 BENCH_NPZ=/tmp/edgeai_bench/bench10k_packed.npz N_BOARD=200 RESET_EACH=1 BOARD_TAG=postreload && python3 board_10k.py'
timeout 20 sshpass -e ssh $OPTS root@$IP 'cd /tmp/edgeai_bench && tar cf - board_gap_postreload.npy' | tar xf - -C "$REPO/results/opt_v2/"
source ${HOME}/miniconda3/etc/profile.d/conda.sh
conda activate edgeai_39
python3 - <<'PY'
import numpy as np
from pathlib import Path
out = (Path(__import__("os").environ["EDGEAI_ROOT"]) / 'results/opt_v2')
b = np.load(out/'board_gap_postreload.npy').astype(np.int32)
c = np.load(out/'v4_csim_gap_prefix_f.npy')
c = np.rint(c[:len(b)] * 1024.0).astype(np.int32)
print('postreload n', len(b), 'max_lsb', int(np.max(np.abs(b-c))))
PY
