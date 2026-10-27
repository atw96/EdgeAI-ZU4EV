#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
# Soak at div1=10, the first divisor whose window matches the requested 149.9 MHz.
# Does not go back to div1=8, where a 0xAA hole showed up at frame 135660.
set -uo pipefail
export SSHPASS="${SSHPASS:?SSHPASS}"
OPTS="-o ConnectTimeout=8 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ServerAliveInterval=15 -o ServerAliveCountMax=160"
IP=${BOARD_IP:?BOARD_IP}
REPO=${EDGEAI_ROOT}
LOG=$REPO/results/opt_v2/logs/v6_soak10.log
exec > >(tee -a "$LOG") 2>&1
echo "[$(date '+%F %T')] soak div1 10"
timeout 20 sshpass -e scp $OPTS ${EDGEAI_ROOT}/scripts/opt_v2/v6_soak10.py root@$IP:/tmp/edgeai_bench/v6_soak10.py
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
ENV='export OUT_DIM=24 OUT_BYTES=96 OUT_LAYOUT=gap_ps OUT_FIXED_SCALE=1024 OUTPUT_PACK_MODE=serial DMA_IOC_TIMEOUT_S=8 PYTHONUNBUFFERED=1 BENCH_NPZ=/tmp/edgeai_bench/bench10k_packed.npz GOLDEN_NPY=/tmp/edgeai_bench/board_gap_v2_rc1.npy SOAK_S=1800'
timeout 60 sshpass -e ssh $OPTS root@$IP "cd /tmp/edgeai_bench && $ENV && python3 v6_divmap.py win 20"
RC=$?
if [ "$RC" != 0 ]; then
  echo "PRECHECK_RC $RC"
  exit "$RC"
fi
timeout 2000 sshpass -e ssh $OPTS root@$IP "cd /tmp/edgeai_bench && $ENV && python3 v6_soak10.py"
RC=$?
echo "SOAK_RC $RC"
exit "$RC"
