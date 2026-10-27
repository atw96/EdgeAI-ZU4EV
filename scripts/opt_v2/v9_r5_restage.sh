#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
# Restage after the reboot, then the 2e6-frame Python cell.
# Clock write, if any, is immediately followed by a reload. DMA starts only
# after fpga0 is operating.
set -uo pipefail
export SSHPASS="${SSHPASS:?SSHPASS}"
OPTS="-o ConnectTimeout=8 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ServerAliveInterval=15 -o ServerAliveCountMax=400"
IP=${BOARD_IP:?BOARD_IP}
H=${EDGEAI_ROOT}
M=${EDGEAI_ROOT}
LOG=$H/results/opt_v2/logs/v9_r5b.log
STAGE=/tmp/v9_r5_stage
mkdir -p "$H/results/opt_v2/logs" "$STAGE"
exec > >(tee -a "$LOG") 2>&1
echo "[$(date '+%F %T')] v9 r5 restage"
cp -f /tmp/v9_stage/cifar10_accel_a2l.bit "$STAGE/cifar10_accel_a2l.bit"
cp -f /tmp/v9_stage/cifar10_accel_rc1.bit "$STAGE/cifar10_accel_rc1.bit"
cp -f "$H/results/opt_v2/bench10k_packed.npz" "$STAGE/bench10k_packed.npz"
cp -f "$H/results/opt_v2/v5_v2/board_gap_v2_rc1.npy" "$STAGE/board_gap_v2_rc1.npy"
cp -f "$H/scripts/dma_infer_common.py" "$STAGE/dma_infer_common.py"
cp -f "$H/scripts/slot32_layout.py" "$STAGE/slot32_layout.py"
cp -f "$H/scripts/board_load_only.sh" "$STAGE/board_load_only.sh"
cp -f "$H/scripts/board_fix_hp0_width.py" "$STAGE/board_fix_hp0_width.py"
cp -f "$M/scripts/opt_v2/v8_x1.py" "$STAGE/v8_x1.py"
cp -f "$M/scripts/opt_v2/v9_r5.py" "$STAGE/v9_r5.py"
cp -f "$M/scripts/opt_v2/v9_r5_remote.sh" "$STAGE/v9_r5_remote.sh"
sed -i 's/\r$//' "$STAGE"/*.py "$STAGE"/*.sh
md5sum "$STAGE/cifar10_accel_a2l.bit" "$STAGE/cifar10_accel_rc1.bit"
timeout 15 sshpass -e ssh $OPTS root@$IP 'mkdir -p /tmp/edgeai_bench'
for f in \
  cifar10_accel_a2l.bit cifar10_accel_rc1.bit \
  bench10k_packed.npz board_gap_v2_rc1.npy \
  dma_infer_common.py slot32_layout.py \
  board_load_only.sh board_fix_hp0_width.py \
  v8_x1.py v9_r5.py v9_r5_remote.sh
do
  echo "SCP $f"
  timeout 90 sshpass -e scp $OPTS "$STAGE/$f" root@$IP:/tmp/edgeai_bench/"$f" || {
    echo "SCP_FAIL $f"
    exit 1
  }
done
echo "[$(date '+%F %T')] soak start"
timeout 7000 sshpass -e ssh $OPTS root@$IP 'sh /tmp/edgeai_bench/v9_r5_remote.sh'
echo R5B_HOST_RC $?
echo "[$(date '+%F %T')] v9 r5 restage done"
