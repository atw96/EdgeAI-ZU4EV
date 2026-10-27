#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
set -euo pipefail
export SSHPASS="${SSHPASS:?SSHPASS}"
OPTS="-o ConnectTimeout=8 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ServerAliveInterval=5 -o ServerAliveCountMax=24"
IP=${BOARD_IP:?BOARD_IP}
H=${EDGEAI_ROOT}
M=${EDGEAI_ROOT}
S=/tmp/v9_stage
copy() {
  echo "SCP $1"
  timeout 180 sshpass -e scp $OPTS "$1" root@$IP:/tmp/edgeai_bench/
}
copy "$M/scripts/opt_v2/v8_x1.py"
copy "$H/scripts/dma_infer_common.py"
copy "$H/scripts/slot32_layout.py"
copy "$H/scripts/board_load_only.sh"
copy "$H/scripts/board_fix_hp0_width.py"
copy "$H/deploy/dense_head.npz"
copy "$H/results/opt_v2/v5_v2/board_gap_v2_rc1.npy"
copy "$H/results/opt_v2/v5_synth/kat_packed.npz"
copy "$H/results/opt_v2/v5_synth/kat_golden.npz"
copy "$S/bench_payloads.bin"
copy "$H/results/opt_v2/bench10k_packed.npz"
sshpass -e ssh $OPTS root@$IP 'cd /tmp/edgeai_bench && chmod +x v8_x2_hot v8_x3 board_load_only.sh && md5sum cifar10_accel_a2l.bit && wc -c bench_payloads.bin bench10k_packed.npz v8_x1.py'
echo SCP_DONE
