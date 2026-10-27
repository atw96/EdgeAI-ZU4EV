#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
# V4 board split + 30 min soak. Target: wsl-local SSH to ${BOARD_IP:?BOARD_IP}.
# One session. DMA only if fpga0 is operating and the firmware MD5 is RC1.
set -euo pipefail
REPO=${EDGEAI_ROOT}
IP=${BOARD_IP:?BOARD_IP}
RC1=$REPO/deploy/opt_v2/A1shallow/cifar10_accel.bit
RC1_MD5=334e27454dcb05d179d6d188b7d404c3
OUT=$REPO/results/opt_v2/v5_v4
export SSHPASS="${SSHPASS:?SSHPASS}"
OPTS="-o ConnectTimeout=8 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ServerAliveInterval=15 -o ServerAliveCountMax=120"
LOG=$REPO/results/opt_v2/logs/v5_v4_board.log
mkdir -p "$OUT" "$REPO/results/opt_v2/logs"
exec > >(tee -a "$LOG") 2>&1
echo "[$(date '+%F %T')] v4 board"
cp -f ${EDGEAI_ROOT}/scripts/dma_infer_common.py "$REPO/scripts/dma_infer_common.py"
cp -f ${EDGEAI_ROOT}/scripts/opt_v2/v5_v4_board.py "$REPO/scripts/opt_v2/v5_v4_board.py"
STATE=$(timeout 20 sshpass -e ssh $OPTS root@$IP 'cat /sys/class/fpga_manager/fpga0/state' || echo unreachable)
echo "state [$STATE]"
if [ "$STATE" != "operating" ]; then
  echo "refuse DMA, PL is not operating"
  exit 1
fi
timeout 40 sshpass -e scp $OPTS \
  "$REPO/scripts/dma_infer_common.py" \
  "$REPO/scripts/slot32_layout.py" \
  "$REPO/scripts/board_fix_hp0_width.py" \
  "$REPO/scripts/opt_v2/v5_v4_board.py" \
  "$REPO/deploy/dense_head.npz" \
  "$REPO/results/opt_v2/bench10k_packed.npz" \
  "$REPO/results/opt_v2/v5_v2/board_gap_v2_rc1.npy" \
  root@$IP:/tmp/edgeai_bench/
timeout 20 sshpass -e ssh $OPTS root@$IP 'cd /tmp/edgeai_bench && python3 board_fix_hp0_width.py'
GOT=$(timeout 20 sshpass -e ssh $OPTS root@$IP 'md5sum /lib/firmware/cifar10_accel.bit' | awk '{print $1}')
echo "firmware $GOT"
test "$GOT" = "$RC1_MD5"
timeout 20 sshpass -e ssh $OPTS root@$IP 'echo CLOCK; cat /sys/kernel/debug/clk/pl0_ref/clk_rate 2>/dev/null || echo no_pl0; echo TEMP; cat /sys/class/thermal/thermal_zone*/temp 2>/dev/null || echo no_temp'
echo "[$(date '+%F %T')] run split+soak"
timeout 4000 sshpass -e ssh $OPTS root@$IP 'cd /tmp/edgeai_bench && export OUT_DIM=24 OUT_BYTES=96 OUT_LAYOUT=gap_ps OUT_FIXED_SCALE=1024 OUTPUT_PACK_MODE=serial DMA_IOC_TIMEOUT_S=8 PYTHONUNBUFFERED=1 DENSE_NPZ=/tmp/edgeai_bench/dense_head.npz BENCH_NPZ=/tmp/edgeai_bench/bench10k_packed.npz GOLDEN_NPY=/tmp/edgeai_bench/board_gap_v2_rc1.npy N_SPLIT=200 N_BURST=100 SOAK_S=1800 && python3 v5_v4_board.py'
timeout 30 sshpass -e ssh $OPTS root@$IP 'cd /tmp/edgeai_bench && tar cf - v4_split.npz' | tar xf - -C "$OUT/"
echo "[$(date '+%F %T')] v4 board fetched"
