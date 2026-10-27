#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
# Python only. PL was just loaded and is operating. No second SSH besides this one.
set -euo pipefail
REPO=${EDGEAI_ROOT}
IP=${BOARD_IP:?BOARD_IP}
export SSHPASS="${SSHPASS:?SSHPASS}"
OPTS="-o ConnectTimeout=8 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ServerAliveInterval=5 -o ServerAliveCountMax=2"
LOG=$REPO/results/opt_v2/logs/v4_board_smoke.log
exec > >(tee -a "$LOG") 2>&1
echo "[$(date '+%F %T')] smoke python, no inner timeout"
timeout 20 sshpass -e ssh $OPTS root@$IP 'cat /sys/class/fpga_manager/fpga0/state'
timeout 70 sshpass -e ssh $OPTS root@$IP 'cd /tmp/edgeai_bench && OUT_DIM=24 OUT_BYTES=96 OUT_LAYOUT=gap_ps OUT_FIXED_SCALE=1024 OUTPUT_PACK_MODE=serial DENSE_NPZ=/tmp/edgeai_bench/dense_head.npz BENCH_NPZ=/tmp/edgeai_bench/cifar10_bench.npz python3 board_smoke8.py'
timeout 20 sshpass -e scp $OPTS \
  root@$IP:/tmp/edgeai_bench/smoke_gap.npy \
  root@$IP:/tmp/edgeai_bench/smoke_lat_ms.npy \
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
print("lat", [round(float(x), 3) for x in lat])
PY
echo "[$(date '+%F %T')] smoke python done"
