#!/bin/bash
# Read-only. No devmem, no DMA, no clock write.
set -uo pipefail
export SSHPASS="${SSHPASS:?SSHPASS}"
OPTS="-o ConnectTimeout=8 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ServerAliveInterval=5 -o ServerAliveCountMax=3"
IP=${BOARD_IP:?BOARD_IP}
timeout 20 sshpass -e ssh $OPTS root@$IP 'echo HOST $(hostname); echo FPGA $(cat /sys/class/fpga_manager/fpga0/state); echo MD5 $(md5sum /lib/firmware/cifar10_accel.bit 2>/dev/null); echo PY; ps | grep -E "v9_r5|v8_x" | grep -v grep; echo UPTIME $(cat /proc/uptime)'
echo PROBE_RC $?
