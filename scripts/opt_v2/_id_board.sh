#!/bin/bash
# Identify the dropbear host. No devmem, no DMA.
set -euo pipefail
export SSHPASS="${SSHPASS:?SSHPASS}"
IP=${BOARD_IP:?BOARD_IP}
OPTS="-o ConnectTimeout=8 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ServerAliveInterval=5 -o ServerAliveCountMax=2"
timeout 20 sshpass -e ssh $OPTS root@$IP 'echo HOST=$(hostname); uname -a; cat /sys/class/fpga_manager/fpga0/state; ip -4 addr show; md5sum /lib/firmware/cifar10_accel.bit 2>/dev/null || true'
