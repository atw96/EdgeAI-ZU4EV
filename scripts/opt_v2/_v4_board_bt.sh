#!/bin/bash
set -euo pipefail
export SSHPASS="${SSHPASS:?SSHPASS}"
OPTS="-o ConnectTimeout=8 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
timeout 25 sshpass -e ssh $OPTS root@${BOARD_IP:?BOARD_IP} 'if [ -x /usr/bin/gdb ]; then gdb -p 3419 -batch -ex "set pagination off" -ex "bt" 2>&1 | head -n 40; else echo NO_GDB; fi; echo ----STAT----; awk "{print}" /proc/3419/stat | cut -d" " -f1-20'
