#!/bin/bash
# Read-only board probe. No DMA, no clock write, no bitstream load.
set -u
export SSHPASS="${SSHPASS:?SSHPASS}"
OPTS="-o ConnectTimeout=8 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
IP=${BOARD_IP:?BOARD_IP}
timeout 20 sshpass -e ssh $OPTS root@$IP 'echo HOST $(hostname); echo FPGA $(cat /sys/class/fpga_manager/fpga0/state); echo BENCH; ls /tmp/edgeai_bench 2>/dev/null | head -40; echo MD5; md5sum /lib/firmware/cifar10_accel.bit 2>/dev/null; echo IIO; ls /sys/bus/iio/devices 2>/dev/null; echo HWMON; ls /sys/class/hwmon 2>/dev/null; echo THERM; ls /sys/class/thermal 2>/dev/null; python3 -c "import tflite_runtime; print(\"tflite_runtime\")" 2>&1 | tail -2; ls -l /tmp/edgeai_bench/model_int8.tflite /tmp/edgeai_bench/v8_x2_hot /tmp/edgeai_bench/v8_x3 /tmp/edgeai_bench/v8_x1.py 2>&1 | head'
