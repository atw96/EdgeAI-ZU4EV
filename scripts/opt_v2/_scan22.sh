#!/bin/bash
# Find a host on the Wi-Fi LAN that accepts TCP/22.
# Target host: wsl-local, scanning the Windows LAN.
set +e
echo "start $(date '+%T')"
for i in $(seq 1 254); do
  ip=${BOARD_SUBNET:?BOARD_SUBNET}.$i
  timeout 0.25 bash -c "echo >/dev/tcp/$ip/22" 2>/dev/null && echo "OPEN $ip" &
done
wait
echo "done $(date '+%T')"
