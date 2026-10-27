#!/bin/bash
# One SSH, no /dev/mem. Used only after the silent 10k SSH has been closed.
set -euo pipefail
export SSHPASS="${SSHPASS:?SSHPASS}"
OPTS="-o ConnectTimeout=8 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
timeout 20 sshpass -e ssh $OPTS root@${BOARD_IP:?BOARD_IP} 'echo STATE; cat /sys/class/fpga_manager/fpga0/state; echo PS; ps | grep -E "python|board_10k" | grep -v grep; echo LS; ls -l /tmp/edgeai_bench/board_*.npy 2>/dev/null || echo no_npy; echo FREE; free; echo UPTIME; uptime'
