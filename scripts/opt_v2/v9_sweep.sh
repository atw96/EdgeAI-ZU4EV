#!/bin/bash
# Find the Xilinx MAC on ${BOARD_SUBNET:?BOARD_SUBNET}.0/24 and try the static ${BOARD_IP:?BOARD_IP} entry.
set -u
echo "[$(date '+%F %T')] sweep"
for i in $(seq 1 254); do
  ping -c 1 -W 1 ${BOARD_SUBNET:?BOARD_SUBNET}.$i >/dev/null 2>&1 &
done
wait
echo "--- arp 00:0a:35 ---"
arp -n | grep -i "00:0a:35" || true
echo "--- try ${BOARD_IP:?BOARD_IP} ---"
ping -c 1 -W 2 ${BOARD_IP:?BOARD_IP} || true
export SSHPASS="${SSHPASS:?SSHPASS}"
OPTS="-o ConnectTimeout=5 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
timeout 12 sshpass -e ssh $OPTS root@${BOARD_IP:?BOARD_IP} 'hostname; cat /sys/class/fpga_manager/fpga0/state' || echo "SSH_1_10_FAIL"
