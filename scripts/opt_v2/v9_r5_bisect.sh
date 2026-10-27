#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
set -uo pipefail
export SSHPASS="${SSHPASS:?SSHPASS}"
OPTS="-o ConnectTimeout=8 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ServerAliveInterval=15 -o ServerAliveCountMax=200"
IP=${BOARD_IP:?BOARD_IP}
H=${EDGEAI_ROOT}
M=${EDGEAI_ROOT}
LOG=$H/results/opt_v2/logs/v9_r5_bisect.log
mkdir -p "$H/results/opt_v2/logs"
exec > >(tee -a "$LOG") 2>&1
echo "[$(date '+%F %T')] v9 r5 bisect"
sed -i 's/\r$//' "$M/scripts/opt_v2/v9_r5_bisect.py" "$M/scripts/opt_v2/v9_r5_bisect_remote.sh"
timeout 40 sshpass -e scp $OPTS "$M/scripts/opt_v2/v9_r5_bisect.py" root@$IP:/tmp/edgeai_bench/v9_r5_bisect.py
timeout 40 sshpass -e scp $OPTS "$M/scripts/opt_v2/v9_r5_bisect_remote.sh" root@$IP:/tmp/edgeai_bench/v9_r5_bisect_remote.sh
timeout 4000 sshpass -e ssh $OPTS root@$IP 'sh /tmp/edgeai_bench/v9_r5_bisect_remote.sh'
echo BISECT_HOST_RC $?
