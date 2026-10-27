#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
# Which divisors actually move the window. Stays at or below the divider that first matched 150 MHz.
set -uo pipefail
export SSHPASS="${SSHPASS:?SSHPASS}"
OPTS="-o ConnectTimeout=8 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
IP=${BOARD_IP:?BOARD_IP}
REPO=${EDGEAI_ROOT}
OUT=$REPO/results/opt_v2/v6
mkdir -p "$OUT"
LOG=$REPO/results/opt_v2/logs/v6_divmap.log
exec > >(tee -a "$LOG") 2>&1
echo "[$(date '+%F %T')] fetch then divmap"
timeout 20 sshpass -e scp $OPTS root@$IP:/tmp/edgeai_bench/ladder.csv "$OUT/ladder.csv" || echo FETCH_CSV_FAIL
timeout 20 sshpass -e scp $OPTS root@$IP:/tmp/edgeai_bench/v6_split.npz "$OUT/v6_split.npz" || echo FETCH_SPLIT_FAIL
timeout 20 sshpass -e scp $OPTS ${EDGEAI_ROOT}/scripts/opt_v2/v6_divmap.py root@$IP:/tmp/edgeai_bench/v6_divmap.py
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
ENV='export OUT_DIM=24 OUT_BYTES=96 OUT_LAYOUT=gap_ps OUT_FIXED_SCALE=1024 OUTPUT_PACK_MODE=serial DMA_IOC_TIMEOUT_S=8 PYTHONUNBUFFERED=1 BENCH_NPZ=/tmp/edgeai_bench/bench10k_packed.npz GOLDEN_NPY=/tmp/edgeai_bench/board_gap_v2_rc1.npy'
for DIV in 14 13 12 11 10; do
  echo "[$(date '+%F %T')] div1 $DIV"
  timeout 20 sshpass -e ssh $OPTS root@$IP "cd /tmp/edgeai_bench && python3 v6_divmap.py set $DIV"
  timeout 40 sshpass -e ssh $OPTS root@$IP 'cd /tmp/edgeai_bench && FORCE_PL_RELOAD=1 sh board_load_only.sh >/tmp/edgeai_bench/load.log 2>&1 && python3 board_fix_hp0_width.py && python3 v6_divmap.py read'
  timeout 15 sshpass -e ssh $OPTS root@$IP 'echo DEBUGFS; cat /sys/kernel/debug/clk/pl0_ref/clk_rate'
  timeout 60 sshpass -e ssh $OPTS root@$IP "cd /tmp/edgeai_bench && $ENV && python3 v6_divmap.py win 40"
  RC=$?
  echo "WIN_RC $RC div1 $DIV"
  if [ "$RC" != 0 ]; then
    exit "$RC"
  fi
done
exit 0
