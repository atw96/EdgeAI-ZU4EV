#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
set -euo pipefail
H=${EDGEAI_ROOT}/deploy/opt_v2/A1shallow/cifar10_accel.hwh
grep -o 'PL0_REF_CTRL__[^"]*' "$H" | head -20
echo '==== clk summary ===='
export SSHPASS="${SSHPASS:?SSHPASS}"
OPTS="-o ConnectTimeout=8 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
timeout 20 sshpass -e ssh $OPTS root@${BOARD_IP:?BOARD_IP} "grep -E 'rpll|iopll|pl0_ref' /sys/kernel/debug/clk/clk_summary | head -40"
timeout 20 sshpass -e scp $OPTS ${EDGEAI_ROOT}/scripts/opt_v2/v6_clk_regs.py root@${BOARD_IP:?BOARD_IP}:/tmp/v6_clk_regs.py
timeout 20 sshpass -e ssh $OPTS root@${BOARD_IP:?BOARD_IP} 'python3 /tmp/v6_clk_regs.py'
