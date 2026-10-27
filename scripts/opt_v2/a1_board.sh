#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
# Load the new bitstream, confirm PL is operating, then 8 DMA latency samples.
# One SSH session at a time. Does not touch deploy/cifar10_accel.bit.
# Target host: wsl-local, then axu4ev-board.
set -euo pipefail
REPO=${EDGEAI_ROOT}
BIT=$REPO/deploy/opt_v2/A1shallow/cifar10_accel.bit
HWH=$REPO/deploy/opt_v2/A1shallow/cifar10_accel.hwh
BOARD=${BOARD_IP:?BOARD_IP}
LOG=$REPO/results/opt_v2/logs/a1_board.log
mkdir -p "$REPO/results/opt_v2/logs"
exec > >(tee -a "$LOG") 2>&1
echo "[$(date '+%F %T')] board latency for A1shallow"
test -f "$BIT"
md5sum "$BIT"
SSH_OPTS="-o ConnectTimeout=8 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ServerAliveInterval=5 -o ServerAliveCountMax=2"
export SSHPASS="${SSHPASS:?SSHPASS}"

echo "---- ssh state ----"
timeout 20 sshpass -e ssh $SSH_OPTS root@$BOARD 'cat /sys/class/fpga_manager/fpga0/state'

echo "---- scp ----"
timeout 60 sshpass -e ssh $SSH_OPTS root@$BOARD 'mkdir -p /tmp/edgeai_bench /lib/firmware /root/firmware'
timeout 60 sshpass -e scp $SSH_OPTS \
  "$BIT" "$HWH" \
  "$REPO/scripts/board_load_only.sh" \
  "$REPO/scripts/board_fix_hp0_width.py" \
  "$REPO/scripts/dma_infer_common.py" \
  "$REPO/scripts/slot32_layout.py" \
  "$REPO/scripts/board_latency_compare.py" \
  "$REPO/deploy/dense_head.npz" \
  "$REPO/deploy/cifar10_bench.npz" \
  root@$BOARD:/tmp/edgeai_bench/

echo "---- install bit and reload PL ----"
timeout 50 sshpass -e ssh $SSH_OPTS root@$BOARD 'cp -f /tmp/edgeai_bench/cifar10_accel.bit /lib/firmware/cifar10_accel.bit; cp -f /tmp/edgeai_bench/cifar10_accel.bit /root/firmware/cifar10_accel.bit; md5sum /lib/firmware/cifar10_accel.bit; FORCE_PL_RELOAD=1 sh /tmp/edgeai_bench/board_load_only.sh'

echo "---- 8-sample latency ----"
timeout 90 sshpass -e ssh $SSH_OPTS root@$BOARD 'cd /tmp/edgeai_bench && OUT_DIM=24 OUT_BYTES=96 OUT_LAYOUT=gap_ps OUT_FIXED_SCALE=1024 OUTPUT_PACK_MODE=serial DENSE_NPZ=dense_head.npz BENCH_NPZ=cifar10_bench.npz N_BENCH=8 N_STREAM=0 N_ACCURACY=0 RUN_CPU=0 HLS_IP_LATENCY_MS=0.877 OUT_JSON=a1shallow_latency.json timeout 45 python3 board_latency_compare.py'

timeout 20 sshpass -e scp $SSH_OPTS root@$BOARD:/tmp/edgeai_bench/a1shallow_latency.json \
  "$REPO/results/opt_v2/a1shallow_latency.json"
echo "[$(date '+%F %T')] board done"
python3 - <<'PY'
import json
from pathlib import Path
p = (Path(__import__("os").environ["EDGEAI_ROOT"]) / 'results/opt_v2/a1shallow_latency.json')
d = json.loads(p.read_text())
fpga = d.get("fpga", {})
print(json.dumps({
    "reset_each": fpga.get("reset_each_dma_ms"),
    "no_reset": fpga.get("no_reset_dma_ms"),
}, indent=2))
PY
