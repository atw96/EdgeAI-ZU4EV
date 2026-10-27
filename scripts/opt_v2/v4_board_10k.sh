#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
# Host: wsl-local launches, axu4ev-board ${BOARD_IP:?BOARD_IP} runs DMA.
# One SSH session. PL must already be operating (smoke loaded A1shallow).
set -euo pipefail
REPO=${EDGEAI_ROOT}
IP=${BOARD_IP:?BOARD_IP}
export SSHPASS="${SSHPASS:?SSHPASS}"
OPTS="-o ConnectTimeout=8 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ServerAliveInterval=15 -o ServerAliveCountMax=40"
LOG=$REPO/results/opt_v2/logs/v4_board_10k.log
mkdir -p "$REPO/results/opt_v2/logs" "$REPO/deploy/opt_v2/known_good"
exec > >(tee -a "$LOG") 2>&1
echo "[$(date '+%F %T')] board 10k"

# Copy, do not rename the live golden bit.
cp -n "$REPO/deploy/cifar10_accel.bit" "$REPO/deploy/opt_v2/known_good/known_good_cifar10_accel.bit" || true
cp -n "$REPO/deploy/cifar10_accel.hwh" "$REPO/deploy/opt_v2/known_good/known_good_cifar10_accel.hwh" || true
md5sum "$REPO/deploy/cifar10_accel.bit" "$REPO/deploy/cifar10_accel.hwh" \
  "$REPO/deploy/opt_v2/A1shallow/cifar10_accel.bit"

STATE=$(timeout 20 sshpass -e ssh $OPTS root@$IP 'cat /sys/class/fpga_manager/fpga0/state')
echo "fpga state: $STATE"
if [ "$STATE" != "operating" ]; then
  echo "PL is not operating; refuse DMA"
  exit 2
fi

timeout 120 sshpass -e scp $OPTS \
  "$REPO/results/opt_v2/bench10k_packed.npz" \
  "$REPO/deploy/dense_head.npz" \
  "$REPO/scripts/dma_infer_common.py" \
  "$REPO/scripts/slot32_layout.py" \
  "$REPO/scripts/opt_v2/board_10k.py" \
  root@$IP:/tmp/edgeai_bench/

echo "[$(date '+%F %T')] reset_each"
timeout 7200 sshpass -e ssh $OPTS root@$IP 'cd /tmp/edgeai_bench && OUT_DIM=24 OUT_BYTES=96 OUT_LAYOUT=gap_ps OUT_FIXED_SCALE=1024 OUTPUT_PACK_MODE=serial DENSE_NPZ=/tmp/edgeai_bench/dense_head.npz BENCH_NPZ=/tmp/edgeai_bench/bench10k_packed.npz N_BOARD=10000 RESET_EACH=1 BOARD_TAG=reset_each DMA_IOC_TIMEOUT_S=5 PYTHONUNBUFFERED=1 python3 board_10k.py'

echo "[$(date '+%F %T')] no_reset"
timeout 7200 sshpass -e ssh $OPTS root@$IP 'cd /tmp/edgeai_bench && OUT_DIM=24 OUT_BYTES=96 OUT_LAYOUT=gap_ps OUT_FIXED_SCALE=1024 OUTPUT_PACK_MODE=serial DENSE_NPZ=/tmp/edgeai_bench/dense_head.npz BENCH_NPZ=/tmp/edgeai_bench/bench10k_packed.npz N_BOARD=10000 RESET_EACH=0 BOARD_TAG=no_reset DMA_IOC_TIMEOUT_S=5 PYTHONUNBUFFERED=1 python3 board_10k.py'

echo "[$(date '+%F %T')] repeat x3 on first 200"
timeout 600 sshpass -e ssh $OPTS root@$IP 'cd /tmp/edgeai_bench && OUT_DIM=24 OUT_BYTES=96 OUT_LAYOUT=gap_ps OUT_FIXED_SCALE=1024 OUTPUT_PACK_MODE=serial DENSE_NPZ=/tmp/edgeai_bench/dense_head.npz BENCH_NPZ=/tmp/edgeai_bench/bench10k_packed.npz N_BOARD=200 RESET_EACH=1 BOARD_TAG=rep1 PYTHONUNBUFFERED=1 python3 board_10k.py && N_BOARD=200 RESET_EACH=1 BOARD_TAG=rep2 python3 board_10k.py && N_BOARD=200 RESET_EACH=1 BOARD_TAG=rep3 python3 board_10k.py'

echo "[$(date '+%F %T')] fetch"
timeout 60 sshpass -e scp $OPTS 'root@'"$IP"':/tmp/edgeai_bench/board_*.npy' "$REPO/results/opt_v2/"
ls -l "$REPO/results/opt_v2"/board_*.npy
echo "[$(date '+%F %T')] board 10k done"
