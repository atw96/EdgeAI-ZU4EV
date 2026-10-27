#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
set -u
export SSHPASS="${SSHPASS:?SSHPASS}"
OPTS="-o ConnectTimeout=8 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
timeout 20 sshpass -e ssh $OPTS root@${BOARD_IP:?BOARD_IP} "cd /tmp/edgeai_bench && sed -i 's/\r$//' v8_x1.py dma_infer_common.py slot32_layout.py board_load_only.sh board_fix_hp0_width.py && echo STRIP_OK"
bash ${EDGEAI_ROOT}/scripts/opt_v2/v9_rc2_boot.sh boot
