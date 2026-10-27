#!/bin/bash
# One retry only. No DMA.
BOARD=${BOARD_IP:?BOARD_IP}
echo ----PING----
ping -c 2 -W 2 "$BOARD" || echo ping_fail
echo ----SSH----
timeout 15 sshpass -p root ssh -o ConnectTimeout=8 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null root@$BOARD 'echo OK; cat /sys/class/fpga_manager/fpga0/state' || echo ssh_fail
