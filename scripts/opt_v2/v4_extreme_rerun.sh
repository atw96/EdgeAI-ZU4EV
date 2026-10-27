#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
# Re-run the 4 extreme frames. Reload PL first if it is not operating.
# Target host for SSH: axu4ev-board ${BOARD_IP:?BOARD_IP}. One session.
set -euo pipefail
REPO=${EDGEAI_ROOT}
IP=${BOARD_IP:?BOARD_IP}
export SSHPASS="${SSHPASS:?SSHPASS}"
OPTS="-o ConnectTimeout=8 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ServerAliveInterval=15"
LOG=$REPO/results/opt_v2/logs/v4_extreme_rerun.log
mkdir -p "$REPO/results/opt_v2/logs"
exec > >(tee -a "$LOG") 2>&1
echo "[$(date '+%F %T')] extreme rerun"
STATE=$(timeout 20 sshpass -e ssh $OPTS root@$IP 'cat /sys/class/fpga_manager/fpga0/state' || true)
echo "state [$STATE]"
timeout 20 sshpass -e ssh $OPTS root@$IP 'mkdir -p /tmp/edgeai_bench /lib/firmware /root/firmware'
if [ "$STATE" != "operating" ]; then
  echo "reload"
  timeout 40 sshpass -e scp $OPTS \
    "$REPO/deploy/opt_v2/A1shallow/cifar10_accel.bit" \
    "$REPO/scripts/board_load_only.sh" \
    "$REPO/scripts/board_fix_hp0_width.py" \
    root@$IP:/tmp/edgeai_bench/
  timeout 40 sshpass -e ssh $OPTS root@$IP 'cp /tmp/edgeai_bench/cifar10_accel.bit /lib/firmware/cifar10_accel.bit; cd /tmp/edgeai_bench && FORCE_PL_RELOAD=1 sh board_load_only.sh'
  STATE=$(timeout 20 sshpass -e ssh $OPTS root@$IP 'cat /sys/class/fpga_manager/fpga0/state')
  echo "state after load [$STATE]"
  if [ "$STATE" != "operating" ]; then
    echo "refuse DMA"
    exit 2
  fi
fi
timeout 40 sshpass -e scp $OPTS \
  "$REPO/results/opt_v2/bench_extreme.npz" \
  "$REPO/scripts/opt_v2/board_10k.py" \
  "$REPO/scripts/dma_infer_common.py" \
  "$REPO/scripts/slot32_layout.py" \
  "$REPO/deploy/dense_head.npz" \
  root@$IP:/tmp/edgeai_bench/
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
    print(tag, 'max_lsb', [int(x) for x in d], 'names', names)
    if d[0] != 0:
        print(tag, 'black board', (b[0]/1024.0).round(3).tolist())
PY
echo "[$(date '+%F %T')] extreme rerun done"
