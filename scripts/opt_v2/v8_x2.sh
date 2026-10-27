#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
# X2 C hot path at the restored 99.94 MHz RC1. Does not write PL0_REF_CTRL.
set -uo pipefail
export SSHPASS="${SSHPASS:?SSHPASS}"
OPTS="-o ConnectTimeout=8 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ServerAliveInterval=15 -o ServerAliveCountMax=120"
IP=${BOARD_IP:?BOARD_IP}
REPO=${EDGEAI_ROOT}
MNT=${EDGEAI_ROOT}
GCC=/tools/Xilinx/Vitis/2020.1/gnu/aarch64/lin/aarch64-linux/bin/aarch64-linux-gnu-gcc
OUT=$REPO/results/opt_v2/v8
LOG=$REPO/results/opt_v2/logs/v8_x2.log
mkdir -p "$OUT" "$REPO/results/opt_v2/logs"
exec > >(tee -a "$LOG") 2>&1
echo "[$(date '+%F %T')] v8 x2"
source ${HOME}/miniconda3/etc/profile.d/conda.sh
conda activate edgeai_39
python3 "$MNT/scripts/opt_v2/v8_x2_prep.py"
"$GCC" -O2 -std=c11 -Wall -o "$OUT/v8_x2_hot" "$MNT/scripts/opt_v2/v8_x2_hot.c"
file "$OUT/v8_x2_hot"
timeout 15 sshpass -e ssh $OPTS root@$IP 'cat /sys/class/fpga_manager/fpga0/state'
timeout 20 sshpass -e ssh $OPTS root@$IP 'mkdir -p /tmp/edgeai_bench'
timeout 30 sshpass -e scp $OPTS "$OUT/v8_x2_hot" "$OUT/dense_w.bin" "$OUT/dense_b.bin" \
  "$OUT/kat_payloads.bin" "$OUT/kat_golden.bin" "$OUT/kat_top1.bin" \
  root@$IP:/tmp/edgeai_bench/
run_hot() {
  timeout "$1" sshpass -e ssh $OPTS root@$IP "cd /tmp/edgeai_bench && ./v8_x2_hot $2"
}
run_hot 30 "bench 19 kat_payloads.bin kat_golden.bin kat_top1.bin dense_w.bin dense_b.bin"
RC=$?
if [ "$RC" != 0 ]; then
  echo "KAT_RC $RC"
  exit "$RC"
fi
timeout 180 sshpass -e scp $OPTS "$OUT/bench_payloads.bin" "$OUT/bench_golden.bin" "$OUT/bench_top1.bin" root@$IP:/tmp/edgeai_bench/
run_hot 60 "bench 200 bench_payloads.bin bench_golden.bin bench_top1.bin dense_w.bin dense_b.bin"
RC=$?
echo "N200_RC $RC"
if [ "$RC" != 0 ]; then
  exit "$RC"
fi
run_hot 180 "bench 10000 bench_payloads.bin bench_golden.bin bench_top1.bin dense_w.bin dense_b.bin"
RC=$?
echo "N10K_RC $RC"
exit "$RC"
