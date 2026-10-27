#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
# 10 million frames on the already-loaded RC2. Does not write PL0_REF_CTRL.
set -uo pipefail
export SSHPASS="${SSHPASS:?SSHPASS}"
OPTS="-o ConnectTimeout=8 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ServerAliveInterval=15 -o ServerAliveCountMax=400"
IP=${BOARD_IP:?BOARD_IP}
H=${EDGEAI_ROOT}
LOG=$H/results/opt_v2/logs/v9_soak10m.log
mkdir -p "$H/results/opt_v2/logs"
exec > >(tee -a "$LOG") 2>&1
echo "[$(date '+%F %T')] rc2 10M soak, clock untouched"
timeout 20 sshpass -e ssh $OPTS root@$IP 'cd /tmp/edgeai_bench && EXPECT_DIV0=10 python3 v8_x1.py readreg && md5sum /lib/firmware/cifar10_accel.bit && cat /sys/class/fpga_manager/fpga0/state'
RC=$?
if [ "$RC" != 0 ]; then
  echo "PRE_RC $RC"
  exit "$RC"
fi
timeout 15 sshpass -e ssh $OPTS root@$IP 'python3 - <<"PY"
base="/sys/bus/iio/devices/iio:device0"
for n in ("in_temp0_ps_temp","in_temp1_remote_temp","in_temp2_pl_temp"):
    raw=float(open(base+"/"+n+"_raw").read())
    off=float(open(base+"/"+n+"_offset").read())
    sc=float(open(base+"/"+n+"_scale").read())
    print("TEMP_START", n, raw, off, sc, (raw+off)*sc)
PY'
timeout 5600 sshpass -e ssh $OPTS root@$IP 'cd /tmp/edgeai_bench && ./v8_x3 10000000 bench_payloads.bin bench_golden.bin'
RC=$?
echo "SOAK_RC $RC"
timeout 20 sshpass -e ssh $OPTS root@$IP 'cd /tmp/edgeai_bench && python3 v8_x1.py readreg; python3 - <<"PY"
base="/sys/bus/iio/devices/iio:device0"
for n in ("in_temp0_ps_temp","in_temp1_remote_temp","in_temp2_pl_temp"):
    raw=float(open(base+"/"+n+"_raw").read())
    off=float(open(base+"/"+n+"_offset").read())
    sc=float(open(base+"/"+n+"_scale").read())
    print("TEMP_END", n, raw, off, sc, (raw+off)*sc)
PY'
exit "$RC"
