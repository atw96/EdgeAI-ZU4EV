#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
# Re-score the 729 synthetic frames with serial GAP decode.
# Target: wsl-local SSH to ${BOARD_IP:?BOARD_IP}. One session. No reload if PL is operating.
set -euo pipefail
REPO=${EDGEAI_ROOT}
IP=${BOARD_IP:?BOARD_IP}
SYN=$REPO/results/opt_v2/v5_synth
export SSHPASS="${SSHPASS:?SSHPASS}"
OPTS="-o ConnectTimeout=8 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ServerAliveInterval=15 -o ServerAliveCountMax=40"
LOG=$REPO/results/opt_v2/logs/v5_synth_rerun.log
mkdir -p "$REPO/results/opt_v2/logs"
exec > >(tee -a "$LOG") 2>&1
echo "[$(date '+%F %T')] synth rerun"
cp -f ${EDGEAI_ROOT}/scripts/dma_infer_common.py "$REPO/scripts/dma_infer_common.py"
if [ -f "$SYN/board_gap_synth.npy" ] && [ ! -f "$SYN/board_gap_synth_holedecode.npy" ]; then
  cp -f "$SYN/board_gap_synth.npy" "$SYN/board_gap_synth_holedecode.npy"
fi
STATE=$(timeout 20 sshpass -e ssh $OPTS root@$IP 'cat /sys/class/fpga_manager/fpga0/state' || echo unreachable)
echo "state [$STATE]"
if [ "$STATE" != "operating" ]; then
  echo "refuse DMA, PL is not operating"
  exit 1
fi
timeout 40 sshpass -e scp $OPTS \
  "$REPO/scripts/dma_infer_common.py" \
  "$REPO/scripts/slot32_layout.py" \
  "$REPO/scripts/board_fix_hp0_width.py" \
  "$REPO/scripts/opt_v2/board_10k.py" \
  "$REPO/deploy/dense_head.npz" \
  "$SYN/synth_packed.npz" \
  root@$IP:/tmp/edgeai_bench/
timeout 20 sshpass -e ssh $OPTS root@$IP 'cd /tmp/edgeai_bench && python3 board_fix_hp0_width.py'
timeout 600 sshpass -e ssh $OPTS root@$IP 'cd /tmp/edgeai_bench && export OUT_DIM=24 OUT_BYTES=96 OUT_LAYOUT=gap_ps OUT_FIXED_SCALE=1024 OUTPUT_PACK_MODE=serial DMA_IOC_TIMEOUT_S=5 PYTHONUNBUFFERED=1 BENCH_NPZ=/tmp/edgeai_bench/synth_packed.npz N_BOARD=729 RESET_EACH=1 BOARD_TAG=synth_serial && python3 board_10k.py'
timeout 30 sshpass -e ssh $OPTS root@$IP 'cd /tmp/edgeai_bench && tar cf - board_gap_synth_serial.npy board_lat_synth_serial.npy' | tar xf - -C "$SYN/"
echo "[$(date '+%F %T')] synth serial fetched"
