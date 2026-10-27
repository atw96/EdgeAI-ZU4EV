#!/bin/bash
# Read-only: why pl0_ref is ~100 MHz. No DMA, no clock writes.
set -euo pipefail
export SSHPASS="${SSHPASS:?SSHPASS}"
OPTS="-o ConnectTimeout=8 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
IP=${BOARD_IP:?BOARD_IP}
timeout 20 sshpass -e ssh $OPTS root@$IP 'echo STATE; cat /sys/class/fpga_manager/fpga0/state; echo MD5; md5sum /lib/firmware/cifar10_accel.bit; echo RATE; cat /sys/kernel/debug/clk/pl0_ref/clk_rate; echo PERMS; ls -l /sys/kernel/debug/clk/pl0_ref/clk_rate; echo PARENT; cat /sys/kernel/debug/clk/pl0_ref/clk_parent 2>/dev/null || echo no_parent; echo SUMMARY; grep -n pl0 /sys/kernel/debug/clk/clk_summary | head -40'
