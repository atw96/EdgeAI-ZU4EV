#!/bin/bash
export SSHPASS="${SSHPASS:?SSHPASS}"
OPTS="-o ConnectTimeout=8 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
timeout 20 sshpass -e ssh $OPTS root@${BOARD_IP:?BOARD_IP} 'echo IIO_NAME; cat /sys/bus/iio/devices/iio:device0/name; echo IIO_LS; ls /sys/bus/iio/devices/iio:device0; echo HWMON_LS; ls -d /sys/class/hwmon/* 2>/dev/null || echo NO_HWMON; echo PY; python3 --version; command -v pip3 || echo NO_PIP'
