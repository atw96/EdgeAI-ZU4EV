#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
set -euo pipefail
export SSHPASS="${SSHPASS:?SSHPASS}"
OPTS="-o ConnectTimeout=8 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
IP=${BOARD_IP:?BOARD_IP}
SRC=${EDGEAI_ROOT}/scripts/opt_v2/v6_kat_debug2.py
timeout 20 sshpass -e scp $OPTS "$SRC" root@$IP:/tmp/edgeai_bench/v6_kat_debug2.py
timeout 60 sshpass -e ssh $OPTS root@$IP 'cd /tmp/edgeai_bench && export OUT_DIM=24 OUT_BYTES=96 OUT_LAYOUT=gap_ps OUT_FIXED_SCALE=1024 OUTPUT_PACK_MODE=serial DMA_IOC_TIMEOUT_S=8 PYTHONUNBUFFERED=1 KAT_NPZ=/tmp/edgeai_bench/kat_packed.npz KAT_GOLDEN=/tmp/edgeai_bench/kat_golden.npz && python3 v6_kat_debug2.py'
