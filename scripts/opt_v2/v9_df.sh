#!/bin/bash
export SSHPASS="${SSHPASS:?SSHPASS}"
OPTS="-o ConnectTimeout=8 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ServerAliveInterval=5"
timeout 15 sshpass -e ssh $OPTS root@${BOARD_IP:?BOARD_IP} 'df -h /tmp /home /root; echo ---; ls -lh /tmp/edgeai_bench 2>/dev/null | head; echo ---; free -m'
