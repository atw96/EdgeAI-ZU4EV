#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
# X4: DIVISOR0=10, reload RC1, KAT, then 3.8e6-frame soak. Restore 15 on failure.
set -uo pipefail
export SSHPASS="${SSHPASS:?SSHPASS}"
OPTS="-o ConnectTimeout=8 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ServerAliveInterval=15 -o ServerAliveCountMax=400"
IP=${BOARD_IP:?BOARD_IP}
REPO=${EDGEAI_ROOT}
LOG=$REPO/results/opt_v2/logs/v8_x4_soak.log
mkdir -p "$REPO/results/opt_v2/logs"
exec > >(tee -a "$LOG") 2>&1
echo "[$(date '+%F %T')] v8 x4 soak DIVISOR0=10"
RESTORING=0
restore() {
  if [ "$RESTORING" = 1 ]; then
    return
  fi
  RESTORING=1
  echo "[$(date '+%F %T')] restore DIVISOR0=15 and RC1"
  timeout 20 sshpass -e ssh $OPTS root@$IP 'cd /tmp/edgeai_bench && python3 v8_x1.py setdiv 15' || echo RESTORE_SET_FAIL
  timeout 20 sshpass -e ssh $OPTS root@$IP 'cp -f /tmp/edgeai_bench/cifar10_accel_rc1.bit /lib/firmware/cifar10_accel.bit; cp -f /tmp/edgeai_bench/cifar10_accel_rc1.bit /root/firmware/cifar10_accel.bit'
  timeout 40 sshpass -e ssh $OPTS root@$IP 'cd /tmp/edgeai_bench && FORCE_PL_RELOAD=1 sh board_load_only.sh' || echo RESTORE_LOAD_FAIL
  timeout 15 sshpass -e ssh $OPTS root@$IP 'cd /tmp/edgeai_bench && EXPECT_DIV0=15 python3 v8_x1.py readreg' || echo RESTORE_REG_FAIL
}
trap restore EXIT
ENV='export OUT_DIM=24 OUT_BYTES=96 OUT_LAYOUT=gap_ps OUT_FIXED_SCALE=1024 OUTPUT_PACK_MODE=serial DMA_IOC_TIMEOUT_S=8 PYTHONUNBUFFERED=1 DENSE_NPZ=/tmp/edgeai_bench/dense_head.npz BENCH_NPZ=/tmp/edgeai_bench/bench10k_packed.npz GOLDEN_NPY=/tmp/edgeai_bench/board_gap_v2_rc1.npy KAT_NPZ=/tmp/edgeai_bench/kat_packed.npz KAT_GOLDEN=/tmp/edgeai_bench/kat_golden.npz LADDER_CSV=/tmp/edgeai_bench/v8_x4_kat.csv'
timeout 15 sshpass -e ssh $OPTS root@$IP 'cat /sys/class/fpga_manager/fpga0/state'
timeout 20 sshpass -e ssh $OPTS root@$IP 'cd /tmp/edgeai_bench && python3 v8_x1.py setdiv 10'
timeout 40 sshpass -e ssh $OPTS root@$IP 'cp -f /tmp/edgeai_bench/cifar10_accel_rc1.bit /lib/firmware/cifar10_accel.bit && cp -f /tmp/edgeai_bench/cifar10_accel_rc1.bit /root/firmware/cifar10_accel.bit && cd /tmp/edgeai_bench && FORCE_PL_RELOAD=1 sh board_load_only.sh'
timeout 15 sshpass -e ssh $OPTS root@$IP "cd /tmp/edgeai_bench && $ENV EXPECT_DIV0=10 && python3 v8_x1.py readreg"
timeout 60 sshpass -e ssh $OPTS root@$IP "cd /tmp/edgeai_bench && $ENV && python3 v8_x1.py kat"
RC=$?
if [ "$RC" != 0 ]; then
  echo "KAT_RC $RC"
  exit "$RC"
fi
timeout 5600 sshpass -e ssh $OPTS root@$IP 'cd /tmp/edgeai_bench && ./v8_x3 3800000 bench_payloads.bin bench_golden.bin'
RC=$?
echo "X4_SOAK_RC $RC"
if [ "$RC" != 0 ]; then
  exit "$RC"
fi
trap - EXIT
echo "[$(date '+%F %T')] keep DIVISOR0=10 RC1 operating"
timeout 15 sshpass -e ssh $OPTS root@$IP 'cd /tmp/edgeai_bench && EXPECT_DIV0=10 python3 v8_x1.py readreg; cat /sys/class/fpga_manager/fpga0/state'
exit 0
