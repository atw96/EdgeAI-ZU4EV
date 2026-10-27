#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
# Load A1shallow and run 8 DMA frames. One SSH at a time. No change to the golden bit.
# Target host: wsl-local, then axu4ev-board at ${BOARD_IP:?BOARD_IP}.
set -euo pipefail
REPO=${EDGEAI_ROOT}
BIT=$REPO/deploy/opt_v2/A1shallow/cifar10_accel.bit
HWH=$REPO/deploy/opt_v2/A1shallow/cifar10_accel.hwh
IP=${BOARD_IP:?BOARD_IP}
LOG=$REPO/results/opt_v2/logs/v4_board_smoke.log
mkdir -p "$REPO/results/opt_v2/logs"
exec > >(tee -a "$LOG") 2>&1
echo "[$(date '+%F %T')] smoke $IP"
md5sum "$BIT"
export SSHPASS="${SSHPASS:?SSHPASS}"
OPTS="-o ConnectTimeout=8 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ServerAliveInterval=5 -o ServerAliveCountMax=2"
timeout 20 sshpass -e ssh $OPTS root@$IP 'echo connected; cat /sys/class/fpga_manager/fpga0/state'
timeout 30 sshpass -e ssh $OPTS root@$IP 'mkdir -p /tmp/edgeai_bench /lib/firmware /root/firmware'
timeout 60 sshpass -e scp $OPTS \
  "$BIT" "$HWH" \
  "$REPO/scripts/board_load_only.sh" \
  "$REPO/scripts/board_fix_hp0_width.py" \
  "$REPO/scripts/dma_infer_common.py" \
  "$REPO/scripts/slot32_layout.py" \
  "$REPO/scripts/opt_v2/board_smoke8.py" \
  "$REPO/deploy/dense_head.npz" \
  "$REPO/deploy/cifar10_bench.npz" \
  root@$IP:/tmp/edgeai_bench/
timeout 50 sshpass -e ssh $OPTS root@$IP 'cp -f /tmp/edgeai_bench/cifar10_accel.bit /lib/firmware/cifar10_accel.bit; cp -f /tmp/edgeai_bench/cifar10_accel.bit /root/firmware/cifar10_accel.bit; md5sum /lib/firmware/cifar10_accel.bit; FORCE_PL_RELOAD=1 sh /tmp/edgeai_bench/board_load_only.sh'
timeout 70 sshpass -e ssh $OPTS root@$IP 'cd /tmp/edgeai_bench && OUT_DIM=24 OUT_BYTES=96 OUT_LAYOUT=gap_ps OUT_FIXED_SCALE=1024 OUTPUT_PACK_MODE=serial DENSE_NPZ=/tmp/edgeai_bench/dense_head.npz BENCH_NPZ=/tmp/edgeai_bench/cifar10_bench.npz timeout 45 python3 board_smoke8.py'
timeout 20 sshpass -e scp $OPTS root@$IP:/tmp/edgeai_bench/smoke_gap.npy root@$IP:/tmp/edgeai_bench/smoke_lat_ms.npy \
  "$REPO/results/opt_v2/"
python3 - <<'PY'
import numpy as np
from pathlib import Path
repo = Path(__import__("os").environ["EDGEAI_ROOT"])
board = np.load(repo / "results/opt_v2/smoke_gap.npy")
lines = (repo / "results/opt_v2/a1_shallow_csim.log").read_text().splitlines()
csim = np.array([[float(x) for x in lines[i].split()] for i in range(len(board))])
d = np.abs(board.astype(np.float64) - csim)
lsb = np.max(np.abs(np.rint(board * 1024) - np.rint(csim * 1024)))
lat = np.load(repo / "results/opt_v2/smoke_lat_ms.npy")
print("max_abs", float(d.max()), "max_lsb", float(lsb), "median_ms", float(np.median(lat)))
print("lat", lat.tolist())
PY
echo "[$(date '+%F %T')] smoke done"
