#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
# S1 clock ladder. Target: wsl-local to ${BOARD_IP:?BOARD_IP}.
# Loads RC1 first because a cold boot leaves fpga0 unknown. Restores 100 MHz in the Python finally.
set -euo pipefail
REPO=${EDGEAI_ROOT}
IP=${BOARD_IP:?BOARD_IP}
RC1=$REPO/deploy/opt_v2/A1shallow/cifar10_accel.bit
RC1_MD5=334e27454dcb05d179d6d188b7d404c3
OUT=$REPO/results/opt_v2/v6
export SSHPASS="${SSHPASS:?SSHPASS}"
OPTS="-o ConnectTimeout=8 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ServerAliveInterval=15 -o ServerAliveCountMax=120"
LOG=$REPO/results/opt_v2/logs/v6_s1.log
mkdir -p "$OUT" "$REPO/results/opt_v2/logs"
exec > >(tee -a "$LOG") 2>&1
echo "[$(date '+%F %T')] v6 s1"
cp -f ${EDGEAI_ROOT}/scripts/dma_infer_common.py "$REPO/scripts/dma_infer_common.py"
timeout 20 sshpass -e ssh $OPTS root@$IP 'mkdir -p /tmp/edgeai_bench /lib/firmware /root/firmware'
timeout 80 sshpass -e scp $OPTS \
  "$RC1" \
  "$REPO/scripts/board_load_only.sh" \
  "$REPO/scripts/board_fix_hp0_width.py" \
  "$REPO/scripts/dma_infer_common.py" \
  "$REPO/scripts/slot32_layout.py" \
  ${EDGEAI_ROOT}/scripts/opt_v2/v6_ladder.py \
  "$REPO/deploy/dense_head.npz" \
  root@$IP:/tmp/edgeai_bench/
timeout 40 sshpass -e ssh $OPTS root@$IP 'cp -f /tmp/edgeai_bench/cifar10_accel.bit /lib/firmware/cifar10_accel.bit; cp -f /tmp/edgeai_bench/cifar10_accel.bit /root/firmware/cifar10_accel.bit; cd /tmp/edgeai_bench && FORCE_PL_RELOAD=1 sh board_load_only.sh'
timeout 20 sshpass -e ssh $OPTS root@$IP 'cd /tmp/edgeai_bench && python3 board_fix_hp0_width.py'
GOT=$(timeout 20 sshpass -e ssh $OPTS root@$IP 'md5sum /lib/firmware/cifar10_accel.bit' | awk '{print $1}')
STATE=$(timeout 20 sshpass -e ssh $OPTS root@$IP 'cat /sys/class/fpga_manager/fpga0/state')
echo "loaded $GOT state $STATE"
test "$GOT" = "$RC1_MD5"
test "$STATE" = "operating"
timeout 180 sshpass -e scp $OPTS \
  "$REPO/results/opt_v2/bench10k_packed.npz" \
  "$REPO/results/opt_v2/v5_v2/board_gap_v2_rc1.npy" \
  "$REPO/results/opt_v2/v5_synth/kat_packed.npz" \
  "$REPO/results/opt_v2/v5_synth/kat_golden.npz" \
  root@$IP:/tmp/edgeai_bench/
echo "[$(date '+%F %T')] ladder"
set +e
timeout 4000 sshpass -e ssh $OPTS root@$IP 'cd /tmp/edgeai_bench && export OUT_DIM=24 OUT_BYTES=96 OUT_LAYOUT=gap_ps OUT_FIXED_SCALE=1024 OUTPUT_PACK_MODE=serial DMA_IOC_TIMEOUT_S=8 PYTHONUNBUFFERED=1 DENSE_NPZ=/tmp/edgeai_bench/dense_head.npz BENCH_NPZ=/tmp/edgeai_bench/bench10k_packed.npz GOLDEN_NPY=/tmp/edgeai_bench/board_gap_v2_rc1.npy KAT_NPZ=/tmp/edgeai_bench/kat_packed.npz KAT_GOLDEN=/tmp/edgeai_bench/kat_golden.npz SOAK_S=1800 && python3 v6_ladder.py'
RC=$?
set -e
echo "python_rc $RC"
timeout 30 sshpass -e ssh $OPTS root@$IP 'cd /tmp/edgeai_bench && tar cf - ladder.csv v6_split.npz' | tar xf - -C "$OUT/" || true
timeout 15 sshpass -e ssh $OPTS root@$IP 'echo RATE; cat /sys/kernel/debug/clk/pl0_ref/clk_rate; echo STATE; cat /sys/class/fpga_manager/fpga0/state'
echo "[$(date '+%F %T')] fetched rc $RC"
exit "$RC"
