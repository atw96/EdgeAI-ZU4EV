#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
set -uo pipefail
export SSHPASS="${SSHPASS:?SSHPASS}"
OPTS="-o ConnectTimeout=8 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ServerAliveInterval=15 -o ServerAliveCountMax=240"
IP=${BOARD_IP:?BOARD_IP}
H=${EDGEAI_ROOT}
M=${EDGEAI_ROOT}
LOG=$H/results/opt_v2/logs/v9_cpu.log
mkdir -p "$H/results/opt_v2/logs"
exec > >(tee -a "$LOG") 2>&1
echo "[$(date '+%F %T')] v9 cpu"
sed -i 's/\r$//' "$M/scripts/opt_v2/v9_cpu.py"
timeout 40 sshpass -e scp $OPTS ${HOME}/tflite_runtime-cp37-aarch64.whl root@$IP:/tmp/edgeai_bench/tflite_runtime.whl
timeout 40 sshpass -e scp $OPTS "$H/deploy/model_int8.tflite" root@$IP:/tmp/edgeai_bench/model_int8.tflite
timeout 40 sshpass -e scp $OPTS "$M/scripts/opt_v2/v9_cpu.py" root@$IP:/tmp/edgeai_bench/v9_cpu.py
timeout 4000 sshpass -e ssh $OPTS root@$IP 'cd /tmp/edgeai_bench && python3 v9_cpu.py'
echo CPU_HOST_RC $?
