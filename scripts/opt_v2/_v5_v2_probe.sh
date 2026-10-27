#!/bin/bash
export SSHPASS="${SSHPASS:?SSHPASS}"
OPTS="-o ConnectTimeout=8 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
timeout 15 sshpass -e ssh $OPTS root@${BOARD_IP:?BOARD_IP} 'echo STATE; cat /sys/class/fpga_manager/fpga0/state; echo PS; ps | grep python | grep -v grep || echo no_python; echo LS; ls -l /tmp/edgeai_bench/board_gap_v2_old.npy /tmp/edgeai_bench/board_lat_v2_old.npy /tmp/edgeai_bench/board_pred_v2_old.npy'
