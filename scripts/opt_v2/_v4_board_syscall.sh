#!/bin/bash
set -euo pipefail
export SSHPASS="${SSHPASS:?SSHPASS}"
OPTS="-o ConnectTimeout=8 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
timeout 25 sshpass -e ssh $OPTS root@${BOARD_IP:?BOARD_IP} 'for i in 1 2 3 4 5; do echo SAMPLE $i; cat /proc/3419/syscall; echo; cat /proc/3419/wchan; echo; sleep 1; done; echo READERS; ls -l /proc/*/fd 2>/dev/null | grep 31899 || echo none'
