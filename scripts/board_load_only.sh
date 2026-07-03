#!/bin/sh
# Load PL bitstream. Default: FORCE reload even if fpga_manager already operating.
set -e

PERSIST=/root/firmware/cifar10_accel.bit
BIT=/lib/firmware/cifar10_accel.bit
FW=/sys/class/fpga_manager/fpga0/firmware
STATE_FILE=/sys/class/fpga_manager/fpga0/state
FORCE_PL_RELOAD="${FORCE_PL_RELOAD:-1}"

mkdir -p /lib/firmware /root/firmware
if [ ! -f "$BIT" ] && [ -f "$PERSIST" ]; then
    cp -f "$PERSIST" "$BIT"
    echo "restored $BIT from $PERSIST"
fi

if [ ! -f "$BIT" ]; then
    echo "ERROR: missing $BIT — upload from PC first"
    exit 1
fi

echo "bit: $(ls -la $BIT)"
md5sum "$BIT" 2>/dev/null || true

CUR=$(cat "$STATE_FILE" 2>/dev/null || echo unknown)
echo "fpga state before load: $CUR"

if [ "$FORCE_PL_RELOAD" = "1" ]; then
    echo "force reload: writing cifar10_accel.bit -> fpga_manager"
    echo cifar10_accel.bit > "$FW"
else
    if [ "$CUR" != "operating" ]; then
        echo "loading cifar10_accel.bit ..."
        echo cifar10_accel.bit > "$FW"
    else
        echo "skip reload (FORCE_PL_RELOAD=0, already operating)"
    fi
fi

i=0
while [ "$i" -lt 30 ]; do
    CUR=$(cat "$STATE_FILE" 2>/dev/null || echo unknown)
    if [ "$CUR" = "operating" ]; then
        break
    fi
    sleep 1
    i=$((i + 1))
done

echo "fpga state after load: $(cat $STATE_FILE)"
echo "--- recent fpga dmesg ---"
dmesg | grep -iE 'fpga_manager|fpga0' | tail -5

if [ "$(cat $STATE_FILE)" != "operating" ]; then
    echo "ERROR: PL load failed"
    exit 1
fi
echo "PL load OK"
if [ -x /tmp/edgeai_bench/board_fix_hp0_width.py ] || [ -f /tmp/edgeai_bench/board_fix_hp0_width.py ]; then
    echo "--- HP0 fabric width 32-bit (AR66295) ---"
    python3 /tmp/edgeai_bench/board_fix_hp0_width.py || true
fi
