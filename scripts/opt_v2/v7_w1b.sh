#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
# Corrected W1. Does not write PL0_REF_CTRL.
set -uo pipefail
export SSHPASS="${SSHPASS:?SSHPASS}"
OPTS="-o ConnectTimeout=8 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ServerAliveInterval=15 -o ServerAliveCountMax=160"
IP=${BOARD_IP:?BOARD_IP}
REPO=${EDGEAI_ROOT}
OUT=$REPO/results/opt_v2/v7
LOG=$REPO/results/opt_v2/logs/v7_w1b.log
mkdir -p "$OUT" "$REPO/results/opt_v2/logs"
exec > >(tee -a "$LOG") 2>&1
echo "[$(date '+%F %T')] v7 w1b"
timeout 20 sshpass -e scp $OPTS ${EDGEAI_ROOT}/scripts/opt_v2/v7_w1b.py root@$IP:/tmp/edgeai_bench/v7_w1b.py
ENV='export OUT_DIM=24 OUT_BYTES=96 OUT_LAYOUT=gap_ps OUT_FIXED_SCALE=1024 OUTPUT_PACK_MODE=serial DMA_IOC_TIMEOUT_S=8 PYTHONUNBUFFERED=1 DENSE_NPZ=/tmp/edgeai_bench/dense_head.npz BENCH_NPZ=/tmp/edgeai_bench/bench10k_packed.npz GOLDEN_NPY=/tmp/edgeai_bench/board_gap_v2_rc1.npy W1_JSON=/tmp/edgeai_bench/v7_w1b.json W1_EVENTS=/tmp/edgeai_bench/v7_events_b.jsonl STRESS_N=20000 ALIGN_N=20000 SOAK_S=1800'
runpy() {
  timeout "$1" sshpass -e ssh $OPTS root@$IP "cd /tmp/edgeai_bench && $ENV && python3 v7_w1b.py $2"
}
runpy 20 "readreg"
RC=$?
if [ "$RC" != 0 ]; then
  echo "READREG_RC $RC"
  exit "$RC"
fi
echo "[$(date '+%F %T')] budget"
runpy 180 "budget"
RC=$?
if [ "$RC" != 0 ]; then
  echo "BUDGET_RC $RC"
  exit "$RC"
fi
echo "[$(date '+%F %T')] stress"
runpy 500 "stress"
RC=$?
if [ "$RC" != 0 ]; then
  echo "STRESS_RC $RC"
  exit "$RC"
fi
echo "[$(date '+%F %T')] align"
runpy 500 "align"
RC=$?
if [ "$RC" != 0 ]; then
  echo "ALIGN_RC $RC"
  exit "$RC"
fi
echo "[$(date '+%F %T')] soak"
runpy 2000 "soak"
RC=$?
echo "SOAK_RC $RC"
timeout 30 sshpass -e ssh $OPTS root@$IP 'cd /tmp/edgeai_bench && tar cf - v7_w1b.json v7_events_b.jsonl' | tar xf - -C "$OUT/" || true
exit "$RC"
