#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
set -euo pipefail
H=${EDGEAI_ROOT}
W=${EDGEAI_ROOT}
# Stop a leftover host-side board script. Do not touch the csim tree.
pkill -f 'scripts/opt_v2/v4_board_10k.sh' || true
sleep 1
export SSHPASS="${SSHPASS:?SSHPASS}"
OPTS="-o ConnectTimeout=8 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
timeout 20 sshpass -e ssh $OPTS root@${BOARD_IP:?BOARD_IP} 'kill 3419 2>/dev/null || true; sleep 1; ps | grep -E "board_10k|python3" | grep -v grep || echo NO_PYTHON; echo STATE; cat /sys/class/fpga_manager/fpga0/state'
cp -f "$W/scripts/opt_v2/board_10k.py" "$H/scripts/opt_v2/board_10k.py"
cp -f "$W/scripts/opt_v2/v4_board_10k.sh" "$H/scripts/opt_v2/v4_board_10k.sh"
chown atw:atw "$H/scripts/opt_v2/board_10k.py" "$H/scripts/opt_v2/v4_board_10k.sh"
chmod +x "$H/scripts/opt_v2/v4_board_10k.sh"
if ! pgrep -f 'v4_csim_10k.sh' >/dev/null; then
  echo CSIM_NOT_RUNNING
fi
su - atw -c "setsid bash $H/scripts/opt_v2/v4_board_10k.sh </dev/null >/dev/null 2>&1 & echo BOARD_RELAUNCHED"
