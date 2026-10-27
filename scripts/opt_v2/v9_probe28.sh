#!/bin/bash
# Read-only board probe. No DMA, no clock write, no bitstream load.
set -u
export SSHPASS="${SSHPASS:?SSHPASS}"
OPTS="-o ConnectTimeout=8 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
IP=${BOARD_IP:?BOARD_IP}
timeout 25 sshpass -e ssh $OPTS root@$IP 'echo HOST $(hostname); echo FPGA $(cat /sys/class/fpga_manager/fpga0/state); echo BENCH; ls /tmp/edgeai_bench 2>/dev/null | head -50; echo MD5; md5sum /lib/firmware/cifar10_accel.bit 2>/dev/null; echo IIO; ls /sys/bus/iio/devices 2>/dev/null; echo HWMON; ls /sys/class/hwmon 2>/dev/null; for h in /sys/class/hwmon/hwmon*; do echo "== $h"; cat $h/name 2>/dev/null; done; echo THERM; ls /sys/class/thermal 2>/dev/null; python3 -c "import tflite_runtime; print(\"tflite_runtime\")" 2>&1 | tail -3; ls -l /tmp/edgeai_bench/v8_x2_hot /tmp/edgeai_bench/v8_x3 /tmp/edgeai_bench/v8_x1.py /tmp/edgeai_bench/cifar10_accel_a2l.bit /tmp/edgeai_bench/cifar10_accel_rc1.bit 2>&1'
timeout 15 sshpass -e ssh $OPTS root@$IP 'cd /tmp/edgeai_bench && EXPECT_DIV0=10 python3 v8_x1.py readreg'
