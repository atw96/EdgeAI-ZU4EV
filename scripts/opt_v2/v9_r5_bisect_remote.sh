#!/bin/sh
cd /tmp/edgeai_bench || exit 1
A2L=cifar10_accel_a2l.bit
RC1=cifar10_accel_rc1.bit
MD5_A2L=395160123c39a98d478e598c9f93e39e
MD5_RC1=334e27454dcb05d179d6d188b7d404c3

div_now() {
    python3 v8_x1.py readreg | sed -n 's/.*"DIVISOR0": \([0-9]*\).*/\1/p'
}
reload() {
    FORCE_PL_RELOAD=1 sh board_load_only.sh
}
restore() {
    echo "RESTORE begin"
    cp -f "$A2L" /lib/firmware/cifar10_accel.bit
    mkdir -p /root/firmware
    cp -f "$A2L" /root/firmware/cifar10_accel.bit || true
    cur=$(div_now)
    echo "RESTORE div_before $cur"
    if [ "$cur" != "10" ]; then
        python3 v8_x1.py setdiv 10
    fi
    reload
    python3 v8_x1.py readreg
    md5sum /lib/firmware/cifar10_accel.bit
    echo "RESTORE end"
}
trap restore EXIT

echo "$MD5_RC1  $RC1" | md5sum -c -
echo "$MD5_A2L  $A2L" | md5sum -c -
cp -f "$RC1" /lib/firmware/cifar10_accel.bit
cur=$(div_now)
echo "BISECT div_before $cur"
if [ "$cur" != "10" ]; then
    python3 v8_x1.py setdiv 10
fi
reload
python3 v8_x1.py readreg
md5sum /lib/firmware/cifar10_accel.bit
cat /sys/class/fpga_manager/fpga0/state

export OUT_DIM=24
export OUT_BYTES=96
export OUT_LAYOUT=gap_ps
export OUTPUT_PACK_MODE=serial
export OUT_FIXED_SCALE=1024
export BENCH_NPZ=/tmp/edgeai_bench/bench10k_packed.npz
export GOLDEN_NPY=/tmp/edgeai_bench/board_gap_v2_rc1.npy
export NFRAMES=200000

for p in ioc len tail; do
    echo "ARM_START $p"
    export PROTECT=$p
    python3 v9_r5_bisect.py
    echo "ARM_RC $p $?"
done
echo BISECT_DONE
