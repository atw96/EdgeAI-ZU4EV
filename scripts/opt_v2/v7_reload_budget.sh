#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
# Reload RC1 without writing PL0_REF_CTRL, then remeasure the time budget.
set -uo pipefail
export SSHPASS="${SSHPASS:?SSHPASS}"
OPTS="-o ConnectTimeout=8 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
IP=${BOARD_IP:?BOARD_IP}
REPO=${EDGEAI_ROOT}
LOG=$REPO/results/opt_v2/logs/v7_reload_budget.log
mkdir -p "$REPO/results/opt_v2/logs" "$REPO/results/opt_v2/v7"
exec > >(tee -a "$LOG") 2>&1
echo "[$(date '+%F %T')] reload then budget"
timeout 15 sshpass -e ssh $OPTS root@$IP 'cat /sys/class/fpga_manager/fpga0/state'
timeout 40 sshpass -e ssh $OPTS root@$IP 'cd /tmp/edgeai_bench && FORCE_PL_RELOAD=1 sh board_load_only.sh'
timeout 20 sshpass -e scp $OPTS ${EDGEAI_ROOT}/scripts/opt_v2/v7_w1b.py root@$IP:/tmp/edgeai_bench/v7_w1b.py
ENV='export OUT_DIM=24 OUT_BYTES=96 OUT_LAYOUT=gap_ps OUT_FIXED_SCALE=1024 OUTPUT_PACK_MODE=serial DMA_IOC_TIMEOUT_S=8 PYTHONUNBUFFERED=1 DENSE_NPZ=/tmp/edgeai_bench/dense_head.npz BENCH_NPZ=/tmp/edgeai_bench/bench10k_packed.npz GOLDEN_NPY=/tmp/edgeai_bench/board_gap_v2_rc1.npy W1_JSON=/tmp/edgeai_bench/v7_w1c.json W1_EVENTS=/tmp/edgeai_bench/v7_events_c.jsonl'
timeout 20 sshpass -e ssh $OPTS root@$IP "cd /tmp/edgeai_bench && $ENV && python3 v7_w1b.py readreg"
RC=$?
if [ "$RC" != 0 ]; then
  echo "READREG_RC $RC"
  exit "$RC"
fi
timeout 120 sshpass -e ssh $OPTS root@$IP "cd /tmp/edgeai_bench && $ENV && python3 v7_w1b.py budget"
RC=$?
echo "BUDGET_RC $RC"
timeout 20 sshpass -e ssh $OPTS root@$IP 'cd /tmp/edgeai_bench && tar cf - v7_w1c.json' | tar xf - -C "$REPO/results/opt_v2/v7/" || true
exit "$RC"
