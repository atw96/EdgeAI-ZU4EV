#!/bin/bash
set -euo pipefail
export SSHPASS="${SSHPASS:?SSHPASS}"
OPTS="-o ConnectTimeout=8 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
timeout 20 sshpass -e ssh $OPTS root@${BOARD_IP:?BOARD_IP} 'kill 3419; sleep 1; ps | grep board_10k | grep -v grep || echo DEAD; cat /sys/class/fpga_manager/fpga0/state'
