#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
# Finish the X3 zero-event count at 99.94 MHz. Does not write PL0_REF_CTRL.
set -uo pipefail
export SSHPASS="${SSHPASS:?SSHPASS}"
OPTS="-o ConnectTimeout=8 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ServerAliveInterval=15 -o ServerAliveCountMax=400"
IP=${BOARD_IP:?BOARD_IP}
REPO=${EDGEAI_ROOT}
LOG=$REPO/results/opt_v2/logs/v8_x3_soak.log
mkdir -p "$REPO/results/opt_v2/logs"
exec > >(tee -a "$LOG") 2>&1
echo "[$(date '+%F %T')] v8 x3 soak 2700000"
timeout 15 sshpass -e ssh $OPTS root@$IP 'cat /sys/class/fpga_manager/fpga0/state'
timeout 5400 sshpass -e ssh $OPTS root@$IP 'cd /tmp/edgeai_bench && ./v8_x3 2700000 bench_payloads.bin bench_golden.bin'
RC=$?
echo "SOAK_RC $RC"
timeout 30 sshpass -e scp $OPTS root@$IP:/tmp/edgeai_bench/v8_x3_events.jsonl "$REPO/results/opt_v2/v8/v8_x3_soak_events.jsonl" || true
exit "$RC"
