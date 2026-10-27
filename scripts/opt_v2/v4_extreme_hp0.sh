#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
# HP0 was still 32-bit, so the first extreme rerun had 0xAA holes. Fix, then rerun.
# Target: axu4ev-board ${BOARD_IP:?BOARD_IP}. PL is already operating. One SSH sequence.
set -euo pipefail
REPO=${EDGEAI_ROOT}
IP=${BOARD_IP:?BOARD_IP}
export SSHPASS="${SSHPASS:?SSHPASS}"
OPTS="-o ConnectTimeout=8 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ServerAliveInterval=15"
LOG=$REPO/results/opt_v2/logs/v4_extreme_rerun.log
exec > >(tee -a "$LOG") 2>&1
echo "[$(date '+%F %T')] hp0 then extreme"
STATE=$(timeout 20 sshpass -e ssh $OPTS root@$IP 'cat /sys/class/fpga_manager/fpga0/state')
echo "state [$STATE]"
if [ "$STATE" != "operating" ]; then
  echo "refuse DMA"
  exit 2
fi
timeout 30 sshpass -e scp $OPTS \
  "$REPO/scripts/dma_infer_common.py" \
  "$REPO/scripts/slot32_layout.py" \
  "$REPO/scripts/board_fix_hp0_width.py" \
  "$REPO/scripts/opt_v2/board_10k.py" \
  "$REPO/results/opt_v2/bench_extreme.npz" \
  "$REPO/deploy/dense_head.npz" \
  root@$IP:/tmp/edgeai_bench/
timeout 20 sshpass -e ssh $OPTS root@$IP 'cd /tmp/edgeai_bench && python3 board_fix_hp0_width.py'
timeout 90 sshpass -e ssh $OPTS root@$IP 'cd /tmp/edgeai_bench && export OUT_DIM=24 OUT_BYTES=96 OUT_LAYOUT=gap_ps OUT_FIXED_SCALE=1024 OUTPUT_PACK_MODE=serial DENSE_NPZ=/tmp/edgeai_bench/dense_head.npz DMA_IOC_TIMEOUT_S=5 PYTHONUNBUFFERED=1 BENCH_NPZ=/tmp/edgeai_bench/bench_extreme.npz N_BOARD=4 RESET_EACH=1 BOARD_TAG=extreme2 && python3 board_10k.py && export BOARD_TAG=extreme3 && python3 board_10k.py'
timeout 20 sshpass -e ssh $OPTS root@$IP 'cd /tmp/edgeai_bench && tar cf - board_gap_extreme2.npy board_gap_extreme3.npy' | tar xf - -C "$REPO/results/opt_v2/"
source ${HOME}/miniconda3/etc/profile.d/conda.sh
conda activate edgeai_39
python3 - <<'PY'
import numpy as np
from pathlib import Path
out = (Path(__import__("os").environ["EDGEAI_ROOT"]) / 'results/opt_v2')
lines = (out/'v4_csim_extreme.log').read_text().splitlines()
csim = np.rint(np.array([[float(x) for x in line.split()] for line in lines[:4]]) * 1024.0)
names = ['black','white','checker','sat']
for tag in ('extreme2','extreme3'):
    b = np.load(out/('board_gap_%s.npy'%tag)).astype(np.int32)
    d = np.max(np.abs(b - csim), axis=1)
    print(tag, list(zip(names, [int(x) for x in d])))
PY
echo "[$(date '+%F %T')] hp0 extreme done"
