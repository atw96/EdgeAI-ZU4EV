#!/bin/bash
# Convert Vivado .bit to ZynqMP fpga_manager-friendly .bin (byte-swapped)
set -e
BIT="${1:-deploy/cifar10_accel.bit}"
OUT="${2:-deploy/cifar10_accel.bin}"
BIF="$(mktemp /tmp/cifar10.XXXX.bif)"
echo "all:{ ${BIT} }" > "$BIF"
bootgen -arch zynqmp -process_bitstream bin -image "$BIF" -w -o "$OUT"
rm -f "$BIF"
ls -la "$OUT"
echo "Load on board: cp to /lib/firmware/cifar10_accel.bin"
echo "  echo cifar10_accel.bin > /sys/class/fpga_manager/fpga0/firmware"
