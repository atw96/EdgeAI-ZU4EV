#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
set -uo pipefail
export SSHPASS="${SSHPASS:?SSHPASS}"
OPTS="-o ConnectTimeout=8 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ServerAliveInterval=15 -o ServerAliveCountMax=200"
IP=${BOARD_IP:?BOARD_IP}
REPO=${EDGEAI_ROOT}
GCC=/tools/Xilinx/Vitis/2020.1/gnu/aarch64/lin/aarch64-linux/bin/aarch64-linux-gnu-gcc
OUT=$REPO/results/opt_v2/v8
LOG=$REPO/results/opt_v2/logs/v8_x2_soak.log
mkdir -p "$REPO/results/opt_v2/logs"
exec > >(tee -a "$LOG") 2>&1
echo "[$(date '+%F %T')] v8 x2 soak 1800s"
"$GCC" -O2 -std=c11 -Wall -o "$OUT/v8_x2_hot" /tmp/v8_x2_hot.c || exit 1
timeout 15 sshpass -e ssh $OPTS root@$IP 'cat /sys/class/fpga_manager/fpga0/state'
timeout 40 sshpass -e scp $OPTS "$OUT/v8_x2_hot" root@$IP:/tmp/edgeai_bench/v8_x2_hot
timeout 1900 sshpass -e ssh $OPTS root@$IP 'cd /tmp/edgeai_bench && ./v8_x2_hot soak 1800 bench_payloads.bin bench_golden.bin bench_top1.bin dense_w.bin dense_b.bin'
RC=$?
echo "SOAK_RC $RC"
exit "$RC"
