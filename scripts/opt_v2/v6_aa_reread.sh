#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
set -uo pipefail
export SSHPASS="${SSHPASS:?SSHPASS}"
OPTS="-o ConnectTimeout=8 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ServerAliveInterval=15 -o ServerAliveCountMax=80"
IP=${BOARD_IP:?BOARD_IP}
REPO=${EDGEAI_ROOT}
LOG=$REPO/results/opt_v2/logs/v6_aa_reread.log
exec > >(tee -a "$LOG") 2>&1
echo "[$(date '+%F %T')] aa reread at div1 10"
timeout 20 sshpass -e scp $OPTS ${EDGEAI_ROOT}/scripts/opt_v2/v6_aa_reread.py root@$IP:/tmp/edgeai_bench/v6_aa_reread.py
RESTORING=0
restore() {
  if [ "$RESTORING" = 1 ]; then
    return
  fi
  RESTORING=1
  echo "[$(date '+%F %T')] restore div1 15"
  timeout 20 sshpass -e ssh $OPTS root@$IP 'cd /tmp/edgeai_bench && python3 v6_divmap.py set 15' || echo RESTORE_SET_FAIL
  timeout 40 sshpass -e ssh $OPTS root@$IP 'cd /tmp/edgeai_bench && FORCE_PL_RELOAD=1 sh board_load_only.sh && python3 board_fix_hp0_width.py && python3 v6_divmap.py read' || echo RESTORE_LOAD_FAIL
}
trap restore EXIT
timeout 20 sshpass -e ssh $OPTS root@$IP 'cd /tmp/edgeai_bench && python3 v6_divmap.py set 10'
timeout 40 sshpass -e ssh $OPTS root@$IP 'cd /tmp/edgeai_bench && FORCE_PL_RELOAD=1 sh board_load_only.sh >/tmp/edgeai_bench/load.log 2>&1 && python3 board_fix_hp0_width.py && python3 v6_divmap.py read'
ENV='export OUT_DIM=24 OUT_BYTES=96 OUT_LAYOUT=gap_ps OUT_FIXED_SCALE=1024 OUTPUT_PACK_MODE=serial DMA_IOC_TIMEOUT_S=8 PYTHONUNBUFFERED=1 BENCH_NPZ=/tmp/edgeai_bench/bench10k_packed.npz CAP=500000'
timeout 1200 sshpass -e ssh $OPTS root@$IP "cd /tmp/edgeai_bench && $ENV && python3 v6_aa_reread.py"
RC=$?
echo "REREAD_RC $RC"
exit "$RC"
