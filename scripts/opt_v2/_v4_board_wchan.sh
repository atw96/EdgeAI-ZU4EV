#!/bin/bash
set -euo pipefail
export SSHPASS="${SSHPASS:?SSHPASS}"
OPTS="-o ConnectTimeout=8 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
timeout 20 sshpass -e ssh $OPTS root@${BOARD_IP:?BOARD_IP} 'echo WCHAN; cat /proc/3419/wchan; echo; echo FD; ls -l /proc/3419/fd; echo STACK; cat /proc/3419/stack 2>/dev/null | head -n 20; echo STAT; cat /proc/3419/status | head -n 15'
