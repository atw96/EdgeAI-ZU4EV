#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
# X1 busy-wait ladder. Write DIVISOR0, then reload RC1, then measure.
# Does not use DIVISOR0=7. Restores DIVISOR0=15 and RC1 on exit.
set -uo pipefail
export SSHPASS="${SSHPASS:?SSHPASS}"
OPTS="-o ConnectTimeout=8 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ServerAliveInterval=15 -o ServerAliveCountMax=80"
IP=${BOARD_IP:?BOARD_IP}
REPO=${EDGEAI_ROOT}
MNT=${EDGEAI_ROOT}
OUT=$REPO/results/opt_v2/v8
LOG=$REPO/results/opt_v2/logs/v8_x1.log
RC1=$REPO/deploy/opt_v2/A1shallow/cifar10_accel.bit
OLD=$REPO/deploy/cifar10_accel.bit
RC1_MD5=334e27454dcb05d179d6d188b7d404c3
OLD_MD5=46987907f8177883048b705fdf68c370
mkdir -p "$OUT" "$REPO/results/opt_v2/logs"
exec > >(tee -a "$LOG") 2>&1
echo "[$(date '+%F %T')] v8 x1"
test "$(md5sum "$RC1" | awk '{print $1}')" = "$RC1_MD5"
test "$(md5sum "$OLD" | awk '{print $1}')" = "$OLD_MD5"
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
timeout 20 sshpass -e ssh $OPTS root@$IP 'mkdir -p /tmp/edgeai_bench /lib/firmware /root/firmware; cat /sys/class/fpga_manager/fpga0/state'
timeout 30 sshpass -e scp $OPTS \
  "$MNT/scripts/opt_v2/v8_x1.py" \
  "$MNT/scripts/dma_infer_common.py" \
  "$MNT/scripts/slot32_layout.py" \
  "$MNT/scripts/board_load_only.sh" \
  "$MNT/scripts/board_fix_hp0_width.py" \
  "$REPO/deploy/dense_head.npz" \
  root@$IP:/tmp/edgeai_bench/
timeout 40 sshpass -e scp $OPTS "$RC1" root@$IP:/tmp/edgeai_bench/cifar10_accel_rc1.bit
timeout 40 sshpass -e scp $OPTS "$OLD" root@$IP:/tmp/edgeai_bench/cifar10_accel_old.bit
timeout 180 sshpass -e scp $OPTS \
  "$REPO/results/opt_v2/bench10k_packed.npz" \
  "$REPO/results/opt_v2/v5_v2/board_gap_v2_rc1.npy" \
  "$REPO/results/opt_v2/v5_synth/kat_packed.npz" \
  "$REPO/results/opt_v2/v5_synth/kat_golden.npz" \
  root@$IP:/tmp/edgeai_bench/
timeout 15 sshpass -e ssh $OPTS root@$IP 'rm -f /tmp/edgeai_bench/v8_ladder.csv'
ENV='export OUT_DIM=24 OUT_BYTES=96 OUT_LAYOUT=gap_ps OUT_FIXED_SCALE=1024 OUTPUT_PACK_MODE=serial DMA_IOC_TIMEOUT_S=8 PYTHONUNBUFFERED=1 DENSE_NPZ=/tmp/edgeai_bench/dense_head.npz BENCH_NPZ=/tmp/edgeai_bench/bench10k_packed.npz GOLDEN_NPY=/tmp/edgeai_bench/board_gap_v2_rc1.npy KAT_NPZ=/tmp/edgeai_bench/kat_packed.npz KAT_GOLDEN=/tmp/edgeai_bench/kat_golden.npz LADDER_CSV=/tmp/edgeai_bench/v8_ladder.csv'
runpy() {
  timeout "$1" sshpass -e ssh $OPTS root@$IP "cd /tmp/edgeai_bench && $ENV && python3 v8_x1.py $2"
}
load_named() {
  timeout 40 sshpass -e ssh $OPTS root@$IP "cp -f /tmp/edgeai_bench/$1 /lib/firmware/cifar10_accel.bit && cp -f /tmp/edgeai_bench/$1 /root/firmware/cifar10_accel.bit && cd /tmp/edgeai_bench && FORCE_PL_RELOAD=1 sh board_load_only.sh"
}
for DIV in 15 12 11 10 9 8; do
  echo "[$(date '+%F %T')] div0 $DIV"
  runpy 20 "setdiv $DIV"
  RC=$?
  if [ "$RC" != 0 ]; then
    echo "SET_RC $RC"
    exit "$RC"
  fi
  load_named cifar10_accel_rc1.bit
  RC=$?
  if [ "$RC" != 0 ]; then
    echo "LOAD_RC $RC"
    exit "$RC"
  fi
  timeout 15 sshpass -e ssh $OPTS root@$IP "cd /tmp/edgeai_bench && $ENV EXPECT_DIV0=$DIV && python3 v8_x1.py readreg"
  RC=$?
  if [ "$RC" != 0 ]; then
    echo "READ_RC $RC div0 $DIV"
    exit "$RC"
  fi
  runpy 60 "kat"
  RC=$?
  if [ "$RC" != 0 ]; then
    echo "KAT_RC $RC div0 $DIV"
    exit "$RC"
  fi
  runpy 120 "n1000"
  RC=$?
  if [ "$RC" != 0 ]; then
    echo "N1000_RC $RC div0 $DIV"
    exit "$RC"
  fi
done
echo "[$(date '+%F %T')] busy-wait 10k A/B at DIVISOR0=15"
runpy 20 "setdiv 15"
load_named cifar10_accel_rc1.bit
timeout 15 sshpass -e ssh $OPTS root@$IP "cd /tmp/edgeai_bench && $ENV EXPECT_DIV0=15 && python3 v8_x1.py readreg"
timeout 180 sshpass -e ssh $OPTS root@$IP "cd /tmp/edgeai_bench && $ENV SAVE_NPZ=/tmp/edgeai_bench/v8_ab_rc1.npz && python3 v8_x1.py n10k rc1"
RC=$?
if [ "$RC" != 0 ]; then
  echo "RC1_10K_RC $RC"
  exit "$RC"
fi
load_named cifar10_accel_old.bit
timeout 15 sshpass -e ssh $OPTS root@$IP "cd /tmp/edgeai_bench && $ENV EXPECT_DIV0=15 && python3 v8_x1.py readreg"
timeout 1000 sshpass -e ssh $OPTS root@$IP "cd /tmp/edgeai_bench && $ENV SAVE_NPZ=/tmp/edgeai_bench/v8_ab_old.npz && python3 v8_x1.py n10k old"
RC=$?
echo "OLD_10K_RC $RC"
timeout 30 sshpass -e ssh $OPTS root@$IP 'cd /tmp/edgeai_bench && tar cf - v8_ladder.csv v8_ab_rc1.npz v8_ab_old.npz' | tar xf - -C "$OUT/" || true
exit "$RC"
