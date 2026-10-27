#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
set -euo pipefail
export SSHPASS="${SSHPASS:?SSHPASS}"
OPTS="-o ConnectTimeout=8 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ServerAliveInterval=5 -o ServerAliveCountMax=12"
IP=${BOARD_IP:?BOARD_IP}
H=${EDGEAI_ROOT}
S=/tmp/v9_stage
sshpass -e ssh $OPTS root@$IP 'mkdir -p /tmp/edgeai_bench'
copy() {
  echo "SCP $1"
  timeout 120 sshpass -e scp $OPTS "$1" root@$IP:/tmp/edgeai_bench/
}
copy "$S/v8_x2_hot"
copy "$S/v8_x3"
copy "$S/bench_golden.bin"
copy "$S/bench_top1.bin"
copy "$S/dense_w.bin"
copy "$S/dense_b.bin"
copy "$S/cifar10_accel_a2l.bit"
copy "$S/cifar10_accel_rc1.bit"
copy "$S/cifar10_accel_old.bit"
copy "$H/scripts/opt_v2/v8_x1.py"
copy "$H/scripts/dma_infer_common.py"
copy "$H/scripts/slot32_layout.py"
copy "$H/scripts/board_load_only.sh"
copy "$H/scripts/board_fix_hp0_width.py"
copy "$H/deploy/dense_head.npz"
copy "$H/results/opt_v2/v5_v2/board_gap_v2_rc1.npy"
copy "$H/results/opt_v2/v5_synth/kat_packed.npz"
copy "$H/results/opt_v2/v5_synth/kat_golden.npz"
echo "SCP payloads"
timeout 180 sshpass -e scp $OPTS "$S/bench_payloads.bin" root@$IP:/tmp/edgeai_bench/
echo "SCP npz"
timeout 180 sshpass -e scp $OPTS "$H/results/opt_v2/bench10k_packed.npz" root@$IP:/tmp/edgeai_bench/
sshpass -e ssh $OPTS root@$IP 'cd /tmp/edgeai_bench && chmod +x v8_x2_hot v8_x3 board_load_only.sh && md5sum cifar10_accel_a2l.bit cifar10_accel_rc1.bit && ls -lh | head'
echo SCP_DONE
