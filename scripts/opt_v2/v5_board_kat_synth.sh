#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
# V1 KAT then the 729-frame synthetic set on RC1.
# Board: ${BOARD_IP:?BOARD_IP}. One SSH sequence. No DMA unless PL is operating.
set -euo pipefail
REPO=${EDGEAI_ROOT}
IP=${BOARD_IP:?BOARD_IP}
SYN=$REPO/results/opt_v2/v5_synth
export SSHPASS="${SSHPASS:?SSHPASS}"
OPTS="-o ConnectTimeout=8 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ServerAliveInterval=15 -o ServerAliveCountMax=40"
LOG=$REPO/results/opt_v2/logs/v5_board.log
mkdir -p "$REPO/results/opt_v2/logs"
exec > >(tee -a "$LOG") 2>&1
echo "[$(date '+%F %T')] v5 board bit md5"
md5sum "$REPO/deploy/opt_v2/A1shallow/cifar10_accel.bit" "$REPO/deploy/cifar10_accel.bit"

load_rc1() {
  timeout 20 sshpass -e ssh $OPTS root@$IP 'mkdir -p /tmp/edgeai_bench /lib/firmware /root/firmware'
  timeout 40 sshpass -e scp $OPTS \
    "$REPO/deploy/opt_v2/A1shallow/cifar10_accel.bit" \
    "$REPO/scripts/board_load_only.sh" \
    "$REPO/scripts/board_fix_hp0_width.py" \
    "$REPO/scripts/dma_infer_common.py" \
    "$REPO/scripts/slot32_layout.py" \
    root@$IP:/tmp/edgeai_bench/
  timeout 40 sshpass -e ssh $OPTS root@$IP 'cp -f /tmp/edgeai_bench/cifar10_accel.bit /lib/firmware/cifar10_accel.bit; cp -f /tmp/edgeai_bench/cifar10_accel.bit /root/firmware/cifar10_accel.bit; cd /tmp/edgeai_bench && FORCE_PL_RELOAD=1 sh board_load_only.sh'
}

timeout 20 sshpass -e ssh $OPTS root@$IP 'mkdir -p /tmp/edgeai_bench'
STATE=$(timeout 20 sshpass -e ssh $OPTS root@$IP 'cat /sys/class/fpga_manager/fpga0/state' || echo unreachable)
echo "state [$STATE]"
if [ "$STATE" != "operating" ]; then
  load_rc1
fi
timeout 20 sshpass -e ssh $OPTS root@$IP 'echo CLOCK; cat /sys/kernel/debug/clk/pl0_ref/clk_rate 2>/dev/null || echo no_pl0; echo TEMP; cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null || echo no_temp; echo MD5; md5sum /lib/firmware/cifar10_accel.bit 2>/dev/null || echo no_bit'
timeout 20 sshpass -e scp $OPTS \
  "$REPO/scripts/dma_infer_common.py" \
  "$REPO/scripts/slot32_layout.py" \
  "$REPO/scripts/board_fix_hp0_width.py" \
  "$REPO/scripts/opt_v2/board_10k.py" \
  "$REPO/deploy/dense_head.npz" \
  "$SYN/kat_packed.npz" \
  "$SYN/synth_packed.npz" \
  root@$IP:/tmp/edgeai_bench/
timeout 20 sshpass -e ssh $OPTS root@$IP 'cd /tmp/edgeai_bench && python3 board_fix_hp0_width.py'
STATE=$(timeout 20 sshpass -e ssh $OPTS root@$IP 'cat /sys/class/fpga_manager/fpga0/state')
echo "state before kat [$STATE]"
if [ "$STATE" != "operating" ]; then
  echo "refuse DMA"
  exit 2
fi

run_tag() {
  local npz="$1" n="$2" tag="$3"
  timeout 600 sshpass -e ssh $OPTS root@$IP "cd /tmp/edgeai_bench && export OUT_DIM=24 OUT_BYTES=96 OUT_LAYOUT=gap_ps OUT_FIXED_SCALE=1024 OUTPUT_PACK_MODE=serial DENSE_NPZ=/tmp/edgeai_bench/dense_head.npz DMA_IOC_TIMEOUT_S=5 PYTHONUNBUFFERED=1 BENCH_NPZ=/tmp/edgeai_bench/${npz} N_BOARD=${n} RESET_EACH=1 BOARD_TAG=${tag} && python3 board_10k.py"
}

run_tag kat_packed.npz 19 kat1
timeout 20 sshpass -e ssh $OPTS root@$IP 'cd /tmp/edgeai_bench && tar cf - board_gap_kat1.npy' | tar xf - -C "$SYN/"
source ${HOME}/miniconda3/etc/profile.d/conda.sh
conda activate edgeai_39
set +e
python3 - <<'PY'
import numpy as np, sys
from pathlib import Path
syn = (Path(__import__("os").environ["EDGEAI_ROOT"]) / 'results/opt_v2/v5_synth')
board = np.load(syn / "board_gap_kat1.npy").astype(np.int32)
gold = np.load(syn / "kat_golden.npz")["gap"]
g = np.rint(gold * 1024.0).astype(np.int32)
d = np.max(np.abs(board - g), axis=1)
print("kat1 max_lsb", [int(x) for x in d])
sys.exit(0 if int(d.max()) == 0 else 1)
PY
KAT_RC=$?
set -e
if [ "$KAT_RC" -ne 0 ]; then
  echo "KAT fail, reload once"
  load_rc1
  timeout 20 sshpass -e scp $OPTS \
    "$REPO/scripts/dma_infer_common.py" "$REPO/scripts/slot32_layout.py" \
    "$REPO/scripts/board_fix_hp0_width.py" "$REPO/scripts/opt_v2/board_10k.py" \
    "$REPO/deploy/dense_head.npz" "$SYN/kat_packed.npz" "$SYN/synth_packed.npz" \
    root@$IP:/tmp/edgeai_bench/
  timeout 20 sshpass -e ssh $OPTS root@$IP 'cd /tmp/edgeai_bench && python3 board_fix_hp0_width.py'
  run_tag kat_packed.npz 19 kat2
  timeout 20 sshpass -e ssh $OPTS root@$IP 'cd /tmp/edgeai_bench && tar cf - board_gap_kat2.npy' | tar xf - -C "$SYN/"
  python3 - <<'PY'
import numpy as np, sys
from pathlib import Path
syn = (Path(__import__("os").environ["EDGEAI_ROOT"]) / 'results/opt_v2/v5_synth')
board = np.load(syn / "board_gap_kat2.npy").astype(np.int32)
gold = np.load(syn / "kat_golden.npz")["gap"]
g = np.rint(gold * 1024.0).astype(np.int32)
d = np.max(np.abs(board - g), axis=1)
print("kat2 max_lsb", [int(x) for x in d])
sys.exit(0 if int(d.max()) == 0 else 1)
PY
fi
echo "KAT pass"
run_tag synth_packed.npz 729 synth
timeout 30 sshpass -e ssh $OPTS root@$IP 'cd /tmp/edgeai_bench && tar cf - board_gap_synth.npy board_lat_synth.npy' | tar xf - -C "$SYN/"
echo "[$(date '+%F %T')] board synth fetched"
