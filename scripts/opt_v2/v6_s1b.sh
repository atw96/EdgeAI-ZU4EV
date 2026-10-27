#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
# Clock ladder. A divisor write glitches a loaded fabric, so each step is:
# write PL0_REF_CTRL, reload RC1, confirm the divisor survived, then DMA.
set -uo pipefail
export SSHPASS="${SSHPASS:?SSHPASS}"
OPTS="-o ConnectTimeout=8 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ServerAliveInterval=15 -o ServerAliveCountMax=120"
IP=${BOARD_IP:?BOARD_IP}
REPO=${EDGEAI_ROOT}
OUT=$REPO/results/opt_v2/v6
LOG=$REPO/results/opt_v2/logs/v6_s1b.log
mkdir -p "$OUT" "$REPO/results/opt_v2/logs"
exec > >(tee -a "$LOG") 2>&1
echo "[$(date '+%F %T')] v6 s1b"
RESTORING=0
restore() {
  if [ "$RESTORING" = 1 ]; then
    return
  fi
  RESTORING=1
  echo "[$(date '+%F %T')] restore 100 MHz and reload"
  timeout 20 sshpass -e ssh $OPTS root@$IP 'cd /tmp/edgeai_bench && python3 v6_step.py set 15' || echo RESTORE_SET_FAIL
  timeout 40 sshpass -e ssh $OPTS root@$IP 'cd /tmp/edgeai_bench && FORCE_PL_RELOAD=1 sh board_load_only.sh && python3 board_fix_hp0_width.py && python3 v6_step.py read' || echo RESTORE_LOAD_FAIL
}
trap restore EXIT
timeout 20 sshpass -e scp $OPTS ${EDGEAI_ROOT}/scripts/opt_v2/v6_step.py root@$IP:/tmp/edgeai_bench/v6_step.py
timeout 15 sshpass -e ssh $OPTS root@$IP 'rm -f /tmp/edgeai_bench/ladder.csv; echo f_mhz,window_ms,p99_ms,max_lsb,div1 > /tmp/edgeai_bench/ladder.csv; cat /sys/class/fpga_manager/fpga0/state'
ENV='export OUT_DIM=24 OUT_BYTES=96 OUT_LAYOUT=gap_ps OUT_FIXED_SCALE=1024 OUTPUT_PACK_MODE=serial DMA_IOC_TIMEOUT_S=8 PYTHONUNBUFFERED=1 DENSE_NPZ=/tmp/edgeai_bench/dense_head.npz BENCH_NPZ=/tmp/edgeai_bench/bench10k_packed.npz GOLDEN_NPY=/tmp/edgeai_bench/board_gap_v2_rc1.npy KAT_NPZ=/tmp/edgeai_bench/kat_packed.npz KAT_GOLDEN=/tmp/edgeai_bench/kat_golden.npz SOAK_S=1800'
runpy() {
  timeout "$1" sshpass -e ssh $OPTS root@$IP "cd /tmp/edgeai_bench && $ENV && python3 v6_step.py $2"
}
echo "[$(date '+%F %T')] split at the already-loaded 100 MHz fabric"
runpy 180 "split"
RC=$?
if [ "$RC" != 0 ]; then
  echo "SPLIT_RC $RC"
  exit "$RC"
fi
for DIV in 15 12 10 9 8; do
  echo "[$(date '+%F %T')] step div1 $DIV"
  runpy 20 "set $DIV"
  RC=$?
  if [ "$RC" != 0 ]; then
    echo "SET_RC $RC"
    exit "$RC"
  fi
  timeout 40 sshpass -e ssh $OPTS root@$IP 'cd /tmp/edgeai_bench && FORCE_PL_RELOAD=1 sh board_load_only.sh >/tmp/edgeai_bench/load.log 2>&1 && python3 board_fix_hp0_width.py && python3 v6_step.py read'
  RC=$?
  if [ "$RC" != 0 ]; then
    echo "RELOAD_RC $RC"
    exit "$RC"
  fi
  GOT=$(timeout 15 sshpass -e ssh $OPTS root@$IP 'cd /tmp/edgeai_bench && python3 v6_step.py read' | awk '/^READ /{print $5}')
  echo "div_after_reload $GOT want $DIV"
  if [ "$GOT" != "$DIV" ]; then
    echo "DIV_LOST"
    exit 6
  fi
  runpy 90 "kat"
  RC=$?
  if [ "$RC" != 0 ]; then
    echo "KAT_RC $RC div1 $DIV"
    exit "$RC"
  fi
  runpy 180 "n1000"
  RC=$?
  if [ "$RC" != 0 ]; then
    echo "N1000_RC $RC div1 $DIV"
    exit "$RC"
  fi
done
echo "[$(date '+%F %T')] 10k and soak at div1 8"
runpy 20 "set 8"
timeout 40 sshpass -e ssh $OPTS root@$IP 'cd /tmp/edgeai_bench && FORCE_PL_RELOAD=1 sh board_load_only.sh >/tmp/edgeai_bench/load.log 2>&1 && python3 board_fix_hp0_width.py && python3 v6_step.py read'
runpy 400 "n10k"
RC=$?
if [ "$RC" != 0 ]; then
  echo "N10K_RC $RC"
  exit "$RC"
fi
runpy 2000 "soak"
RC=$?
echo "SOAK_RC $RC"
timeout 30 sshpass -e ssh $OPTS root@$IP 'cd /tmp/edgeai_bench && tar cf - ladder.csv v6_split.npz' | tar xf - -C "$OUT/" || true
exit "$RC"
