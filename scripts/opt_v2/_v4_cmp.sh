#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
set -euo pipefail
REPO=${EDGEAI_ROOT}
export SSHPASS="${SSHPASS:?SSHPASS}"
OPTS="-o ConnectTimeout=8 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
timeout 20 sshpass -e scp $OPTS root@${BOARD_IP:?BOARD_IP}:/tmp/edgeai_bench/smoke_lat_ms.npy "$REPO/results/opt_v2/smoke_lat_ms.npy"
python3 - <<'PY'
import numpy as np
from pathlib import Path
repo = Path(__import__("os").environ["EDGEAI_ROOT"])
board = np.load(repo / "results/opt_v2/smoke_gap.npy")
lines = (repo / "results/opt_v2/a1_shallow_csim.log").read_text().splitlines()
csim = np.array([[float(x) for x in lines[i].split()] for i in range(len(board))])
d = np.abs(board.astype(np.float64) - csim)
lsb = np.abs(np.rint(board * 1024) - np.rint(csim * 1024))
lat = np.load(repo / "results/opt_v2/smoke_lat_ms.npy")
print("shape", board.shape, csim.shape)
print("max_abs", float(d.max()), "max_lsb", float(lsb.max()))
print("median_ms", float(np.median(lat)), "p99", float(np.percentile(lat, 99)))
print("lat", [round(float(x), 4) for x in lat])
print("frame0_board", [round(float(x), 6) for x in board[0][:4]])
print("frame0_csim", [round(float(x), 6) for x in csim[0][:4]])
PY
