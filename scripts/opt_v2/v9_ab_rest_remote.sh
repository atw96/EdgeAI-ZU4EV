#!/bin/sh
cd /tmp/edgeai_bench || exit 1
A2L=cifar10_accel_a2l.bit
OLD=cifar10_accel_old.bit
MD5_A2L=395160123c39a98d478e598c9f93e39e
MD5_OLD=46987907f8177883048b705fdf68c370

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

echo "REST_PRECHECK"
echo "$MD5_A2L  $A2L" | md5sum -c -
echo "$MD5_OLD  $OLD" | md5sum -c -
python3 v8_x1.py readreg

load_cell() {
    name=$1
    src=$2
    div=$3
    echo "LOAD $name div $div"
    cp -f "$src" /lib/firmware/cifar10_accel.bit
    mkdir -p /root/firmware
    cp -f "$src" /root/firmware/cifar10_accel.bit || true
    cur=$(div_now)
    echo "LOAD div_before $cur"
    if [ "$cur" != "$div" ]; then
        python3 v8_x1.py setdiv "$div"
    fi
    reload
    python3 v8_x1.py readreg
    md5sum /lib/firmware/cifar10_accel.bit
    cat /sys/class/fpga_manager/fpga0/state
}
run3() {
    tag=$1
    bin=$2
    i=1
    while [ "$i" -le 3 ]; do
        echo "CELL $tag rep $i"
        ./$bin bench 10000 bench_payloads.bin bench_golden.bin bench_top1.bin dense_w.bin dense_b.bin
        rc=$?
        echo "CELL_RC $tag $i $rc"
        if [ "$rc" -ne 0 ]; then
            echo "AB_FAIL $tag"
            exit "$rc"
        fi
        i=$((i + 1))
    done
}

load_cell old_99 "$OLD" 15
run3 old_99 v9_x2_count
load_cell rc2_99 "$A2L" 15
run3 rc2_99 v8_x2_hot
echo AB_REST_DONE
