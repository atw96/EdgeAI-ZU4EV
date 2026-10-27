#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
# RC2 startup. Write DIVISOR0=10, then reload, then KAT and a 100-frame wait check.
# Refuses to continue when the wait is not 0.384 ms +/- 5%.
# Target host: wsl-local ssh to axu4ev-board. Does not modify deploy bits.
set -uo pipefail
export SSHPASS="${SSHPASS:?SSHPASS}"
OPTS="-o ConnectTimeout=8 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ServerAliveInterval=15 -o ServerAliveCountMax=40"
IP=${BOARD_IP:?BOARD_IP}
H=${EDGEAI_ROOT}
LOG=$H/results/opt_v2/logs/v9_rc2_boot.log
mkdir -p "$H/results/opt_v2/logs"
exec > >(tee -a "$LOG") 2>&1
echo "[$(date '+%F %T')] rc2 boot"
MODE=${1:-boot}
RESTORING=0
restore_rc1() {
  if [ "$RESTORING" = 1 ]; then
    return
  fi
  RESTORING=1
  echo "[$(date '+%F %T')] restore RC1 bit, leave the clock register as it is"
  timeout 20 sshpass -e ssh $OPTS root@$IP 'cp -f /tmp/edgeai_bench/cifar10_accel_rc1.bit /lib/firmware/cifar10_accel.bit; cp -f /tmp/edgeai_bench/cifar10_accel_rc1.bit /root/firmware/cifar10_accel.bit' || echo RESTORE_CP_FAIL
  timeout 40 sshpass -e ssh $OPTS root@$IP 'cd /tmp/edgeai_bench && FORCE_PL_RELOAD=1 sh board_load_only.sh' || echo RESTORE_LOAD_FAIL
}
trap restore_rc1 EXIT
timeout 15 sshpass -e ssh $OPTS root@$IP 'cat /sys/class/fpga_manager/fpga0/state; cd /tmp/edgeai_bench && python3 v8_x1.py readreg'
if [ "$MODE" = "guard" ]; then
  echo "[$(date '+%F %T')] guard: DIVISOR0=15 then reload RC2, expect the wait check to refuse"
  timeout 20 sshpass -e ssh $OPTS root@$IP 'cd /tmp/edgeai_bench && python3 v8_x1.py setdiv 15'
  BIT=cifar10_accel_a2l.bit
else
  timeout 20 sshpass -e ssh $OPTS root@$IP 'cd /tmp/edgeai_bench && python3 v8_x1.py setdiv 10'
  BIT=cifar10_accel_a2l.bit
fi
timeout 20 sshpass -e ssh $OPTS root@$IP "cp -f /tmp/edgeai_bench/$BIT /lib/firmware/cifar10_accel.bit && cp -f /tmp/edgeai_bench/$BIT /root/firmware/cifar10_accel.bit && md5sum /lib/firmware/cifar10_accel.bit"
timeout 40 sshpass -e ssh $OPTS root@$IP 'cd /tmp/edgeai_bench && FORCE_PL_RELOAD=1 sh board_load_only.sh'
RC=$?
if [ "$RC" != 0 ]; then
  echo "LOAD_RC $RC"
  exit "$RC"
fi
EXPECT=10
if [ "$MODE" = "guard" ]; then
  EXPECT=15
fi
timeout 15 sshpass -e ssh $OPTS root@$IP "cd /tmp/edgeai_bench && EXPECT_DIV0=$EXPECT python3 v8_x1.py readreg && cat /sys/class/fpga_manager/fpga0/state"
RC=$?
if [ "$RC" != 0 ]; then
  echo "REG_RC $RC"
  exit "$RC"
fi
if [ "$MODE" != "guard" ]; then
  ENV='export OUT_DIM=24 OUT_BYTES=96 OUT_LAYOUT=gap_ps OUT_FIXED_SCALE=1024 OUTPUT_PACK_MODE=serial DMA_IOC_TIMEOUT_S=8 PYTHONUNBUFFERED=1 DENSE_NPZ=/tmp/edgeai_bench/dense_head.npz BENCH_NPZ=/tmp/edgeai_bench/bench10k_packed.npz GOLDEN_NPY=/tmp/edgeai_bench/board_gap_v2_rc1.npy KAT_NPZ=/tmp/edgeai_bench/kat_packed.npz KAT_GOLDEN=/tmp/edgeai_bench/kat_golden.npz LADDER_CSV=/tmp/edgeai_bench/v9_kat.csv'
  timeout 60 sshpass -e ssh $OPTS root@$IP "cd /tmp/edgeai_bench && $ENV && python3 v8_x1.py kat"
  RC=$?
  if [ "$RC" != 0 ]; then
    echo "KAT_RC $RC"
    exit "$RC"
  fi
fi
timeout 60 sshpass -e ssh $OPTS root@$IP 'cd /tmp/edgeai_bench && ./v8_x2_hot bench 100 bench_payloads.bin bench_golden.bin bench_top1.bin dense_w.bin dense_b.bin' | tee "$H/results/opt_v2/logs/v9_wait_check.txt"
RC=${PIPESTATUS[0]}
echo "WAIT_RC $RC"
if [ "$RC" != 0 ]; then
  exit "$RC"
fi
python3 - << 'PY'
import json, sys
from pathlib import Path
text = (Path(__import__("os").environ["EDGEAI_ROOT"]) / 'results/opt_v2/logs/v9_wait_check.txt').read_text(errors="replace")
line = [ln for ln in text.splitlines() if ln.startswith("POINT ")][-1]
row = json.loads(line[len("POINT "):])
wait = float(row["wait_ms"])
lo, hi = 0.3837 * 0.95, 0.3837 * 1.05
print("WAIT_CHECK", wait, "band", round(lo, 4), round(hi, 4))
mode = sys.argv[1] if False else open("/tmp/v9_boot_mode","w")
ok = lo <= wait <= hi
Path("/tmp/v9_wait_ok").write_text("1\n" if ok else "0\n")
print("IN_BAND", ok)
PY
# The python above always writes the flag. Guard must be OUT of band. Boot must be IN band.
IN_BAND=$(cat /tmp/v9_wait_ok)
if [ "$MODE" = "guard" ]; then
  if [ "$IN_BAND" = "1" ]; then
    echo "GUARD_FAIL clock looked like 149.9 MHz"
    exit 8
  fi
  echo "GUARD_REFUSED"
  exit 0
fi
if [ "$IN_BAND" != "1" ]; then
  echo "BOOT_REFUSED wait outside 0.384 ms +/- 5%"
  exit 9
fi
trap - EXIT
echo "[$(date '+%F %T')] RC2 boot accepted"
exit 0
