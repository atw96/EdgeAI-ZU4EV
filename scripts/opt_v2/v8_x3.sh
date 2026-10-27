#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
# X3 delay histogram at the restored 99.94 MHz RC1. Does not write PL0_REF_CTRL.
set -uo pipefail
export SSHPASS="${SSHPASS:?SSHPASS}"
OPTS="-o ConnectTimeout=8 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ServerAliveInterval=15 -o ServerAliveCountMax=80"
IP=${BOARD_IP:?BOARD_IP}
REPO=${EDGEAI_ROOT}
MNT=${EDGEAI_ROOT}
GCC=/tools/Xilinx/Vitis/2020.1/gnu/aarch64/lin/aarch64-linux/bin/aarch64-linux-gnu-gcc
OUT=$REPO/results/opt_v2/v8
LOG=$REPO/results/opt_v2/logs/v8_x3.log
mkdir -p "$OUT" "$REPO/results/opt_v2/logs"
exec > >(tee -a "$LOG") 2>&1
echo "[$(date '+%F %T')] v8 x3"
sed -i 's/\r$//' "$MNT/scripts/opt_v2/v8_x3.c" || true
"$GCC" -O2 -std=c11 -Wall -o "$OUT/v8_x3" "$MNT/scripts/opt_v2/v8_x3.c" || exit 1
file "$OUT/v8_x3"
STATE=$(timeout 15 sshpass -e ssh $OPTS root@$IP 'cat /sys/class/fpga_manager/fpga0/state')
echo "state $STATE"
if [ "$STATE" != "operating" ]; then
  echo "PL not operating; reload RC1 before any DMA"
  exit 2
fi
timeout 20 sshpass -e ssh $OPTS root@$IP 'mkdir -p /tmp/edgeai_bench; ls -l /tmp/edgeai_bench/bench_payloads.bin /tmp/edgeai_bench/bench_golden.bin'
RC=$?
if [ "$RC" != 0 ]; then
  timeout 180 sshpass -e scp $OPTS "$OUT/bench_payloads.bin" "$OUT/bench_golden.bin" root@$IP:/tmp/edgeai_bench/
fi
timeout 30 sshpass -e scp $OPTS "$OUT/v8_x3" root@$IP:/tmp/edgeai_bench/v8_x3
timeout 400 sshpass -e ssh $OPTS root@$IP 'cd /tmp/edgeai_bench && ./v8_x3 100000 bench_payloads.bin bench_golden.bin'
RC=$?
echo "X3_RC $RC"
timeout 30 sshpass -e scp $OPTS root@$IP:/tmp/edgeai_bench/v8_x3_events.jsonl "$OUT/v8_x3_events.jsonl" || true
exit "$RC"
