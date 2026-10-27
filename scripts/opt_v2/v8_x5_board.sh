#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
# Load the A2-L bitstream without writing PL0_REF_CTRL. KAT, then 10k vs RC1 golden.
# On failure, reload RC1 and leave DIVISOR0 alone.
set -uo pipefail
export SSHPASS="${SSHPASS:?SSHPASS}"
OPTS="-o ConnectTimeout=8 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ServerAliveInterval=15 -o ServerAliveCountMax=40"
IP=${BOARD_IP:?BOARD_IP}
H=${EDGEAI_ROOT}
LOG=$H/results/opt_v2/logs/v8_x5_board.log
BIT=$H/results/opt_v2/a2l/cifar10_accel.bit
mkdir -p "$H/results/opt_v2/logs"
exec > >(tee -a "$LOG") 2>&1
echo "[$(date '+%F %T')] x5 board A2-L, clock register untouched"
RESTORING=0
restore_rc1() {
  if [ "$RESTORING" = 1 ]; then
    return
  fi
  RESTORING=1
  echo "[$(date '+%F %T')] restore RC1 bit, keep DIVISOR0"
  timeout 20 sshpass -e ssh $OPTS root@$IP 'cp -f /tmp/edgeai_bench/cifar10_accel_rc1.bit /lib/firmware/cifar10_accel.bit; cp -f /tmp/edgeai_bench/cifar10_accel_rc1.bit /root/firmware/cifar10_accel.bit' || echo RESTORE_CP_FAIL
  timeout 40 sshpass -e ssh $OPTS root@$IP 'cd /tmp/edgeai_bench && FORCE_PL_RELOAD=1 sh board_load_only.sh' || echo RESTORE_LOAD_FAIL
  timeout 15 sshpass -e ssh $OPTS root@$IP 'cd /tmp/edgeai_bench && EXPECT_DIV0=10 python3 v8_x1.py readreg' || echo RESTORE_REG_FAIL
}
trap restore_rc1 EXIT
timeout 15 sshpass -e ssh $OPTS root@$IP 'cat /sys/class/fpga_manager/fpga0/state'
timeout 40 sshpass -e scp $OPTS "$BIT" root@$IP:/tmp/edgeai_bench/cifar10_accel_a2l.bit
timeout 20 sshpass -e ssh $OPTS root@$IP 'md5sum /tmp/edgeai_bench/cifar10_accel_a2l.bit; cp -f /tmp/edgeai_bench/cifar10_accel_a2l.bit /lib/firmware/cifar10_accel.bit; cp -f /tmp/edgeai_bench/cifar10_accel_a2l.bit /root/firmware/cifar10_accel.bit'
timeout 40 sshpass -e ssh $OPTS root@$IP 'cd /tmp/edgeai_bench && FORCE_PL_RELOAD=1 sh board_load_only.sh'
RC=$?
if [ "$RC" != 0 ]; then
  echo "LOAD_RC $RC"
  exit "$RC"
fi
timeout 15 sshpass -e ssh $OPTS root@$IP 'cd /tmp/edgeai_bench && EXPECT_DIV0=10 python3 v8_x1.py readreg && md5sum /lib/firmware/cifar10_accel.bit && cat /sys/class/fpga_manager/fpga0/state'
RC=$?
if [ "$RC" != 0 ]; then
  echo "REG_RC $RC"
  exit "$RC"
fi
ENV='export OUT_DIM=24 OUT_BYTES=96 OUT_LAYOUT=gap_ps OUT_FIXED_SCALE=1024 OUTPUT_PACK_MODE=serial DMA_IOC_TIMEOUT_S=8 PYTHONUNBUFFERED=1 DENSE_NPZ=/tmp/edgeai_bench/dense_head.npz BENCH_NPZ=/tmp/edgeai_bench/bench10k_packed.npz GOLDEN_NPY=/tmp/edgeai_bench/board_gap_v2_rc1.npy KAT_NPZ=/tmp/edgeai_bench/kat_packed.npz KAT_GOLDEN=/tmp/edgeai_bench/kat_golden.npz LADDER_CSV=/tmp/edgeai_bench/v8_x5_kat.csv'
timeout 60 sshpass -e ssh $OPTS root@$IP "cd /tmp/edgeai_bench && $ENV && python3 v8_x1.py kat"
RC=$?
if [ "$RC" != 0 ]; then
  echo "KAT_RC $RC"
  exit "$RC"
fi
timeout 180 sshpass -e ssh $OPTS root@$IP 'cd /tmp/edgeai_bench && ./v8_x2_hot bench 10000 bench_payloads.bin bench_golden.bin bench_top1.bin dense_w.bin dense_b.bin'
RC=$?
echo "BENCH_RC $RC"
if [ "$RC" != 0 ]; then
  exit "$RC"
fi
trap - EXIT
echo "[$(date '+%F %T')] A2-L left loaded, DIVISOR0 unchanged"
exit 0
