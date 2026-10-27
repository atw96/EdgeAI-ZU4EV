#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
# V2: known_good then RC1, same packed 10k, same timer, same day.
# Target host: wsl-local. Board: ${BOARD_IP:?BOARD_IP}. One SSH at a time.
# Timer is inside board_10k.py: start_transfer -> wait_ioc. Dense is after that.
set -euo pipefail
set -o errtrace
REPO=${EDGEAI_ROOT}
IP=${BOARD_IP:?BOARD_IP}
OUT=$REPO/results/opt_v2/v5_v2
OLD=$REPO/deploy/cifar10_accel.bit
RC1=$REPO/deploy/opt_v2/A1shallow/cifar10_accel.bit
OLD_MD5=46987907f8177883048b705fdf68c370
RC1_MD5=334e27454dcb05d179d6d188b7d404c3
NPZ=$REPO/results/opt_v2/bench10k_packed.npz
export SSHPASS="${SSHPASS:?SSHPASS}"
OPTS="-o ConnectTimeout=8 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ServerAliveInterval=15 -o ServerAliveCountMax=120"
LOG=$REPO/results/opt_v2/logs/v5_v2.log
mkdir -p "$OUT" "$REPO/results/opt_v2/logs"
exec > >(tee -a "$LOG") 2>&1
echo "[$(date '+%F %T')] v2 start"
test -f "$NPZ"
md5sum "$OLD" "$RC1"
cp -f ${EDGEAI_ROOT}/scripts/dma_infer_common.py "$REPO/scripts/dma_infer_common.py"
cp -f ${EDGEAI_ROOT}/results/opt_v2/v5_v32_rootcause.json "$REPO/results/opt_v2/v5_v32_rootcause.json" || true

restore_rc1() {
  echo "[$(date '+%F %T')] restore RC1 after error"
  timeout 60 sshpass -e scp $OPTS "$RC1" root@$IP:/tmp/edgeai_bench/cifar10_accel.bit || true
  timeout 60 sshpass -e ssh $OPTS root@$IP 'cp -f /tmp/edgeai_bench/cifar10_accel.bit /lib/firmware/cifar10_accel.bit; cp -f /tmp/edgeai_bench/cifar10_accel.bit /root/firmware/cifar10_accel.bit; cd /tmp/edgeai_bench && FORCE_PL_RELOAD=1 sh board_load_only.sh' || true
}
trap restore_rc1 ERR

load_bit() {
  local src="$1" expect="$2"
  timeout 80 sshpass -e scp $OPTS "$src" root@$IP:/tmp/edgeai_bench/cifar10_accel.bit
  timeout 80 sshpass -e ssh $OPTS root@$IP 'cp -f /tmp/edgeai_bench/cifar10_accel.bit /lib/firmware/cifar10_accel.bit; cp -f /tmp/edgeai_bench/cifar10_accel.bit /root/firmware/cifar10_accel.bit; cd /tmp/edgeai_bench && FORCE_PL_RELOAD=1 sh board_load_only.sh'
  timeout 20 sshpass -e ssh $OPTS root@$IP 'cd /tmp/edgeai_bench && python3 board_fix_hp0_width.py'
  local got state
  got=$(timeout 20 sshpass -e ssh $OPTS root@$IP 'md5sum /lib/firmware/cifar10_accel.bit' | awk '{print $1}')
  state=$(timeout 20 sshpass -e ssh $OPTS root@$IP 'cat /sys/class/fpga_manager/fpga0/state')
  echo "loaded md5 $got state $state expect $expect"
  test "$got" = "$expect"
  test "$state" = "operating"
}

run_board() {
  local npz="$1" n="$2" tag="$3" tout="$4"
  timeout "$tout" sshpass -e ssh $OPTS root@$IP "cd /tmp/edgeai_bench && export OUT_DIM=24 OUT_BYTES=96 OUT_LAYOUT=gap_ps OUT_FIXED_SCALE=1024 OUTPUT_PACK_MODE=serial DMA_IOC_TIMEOUT_S=8 PYTHONUNBUFFERED=1 BENCH_NPZ=/tmp/edgeai_bench/${npz} N_BOARD=${n} RESET_EACH=1 BOARD_TAG=${tag} && python3 board_10k.py"
  timeout 60 sshpass -e ssh $OPTS root@$IP "cd /tmp/edgeai_bench && tar cf - board_gap_${tag}.npy board_pred_${tag}.npy board_lat_${tag}.npy" | tar xf - -C "$OUT/"
}

timeout 20 sshpass -e ssh $OPTS root@$IP 'mkdir -p /tmp/edgeai_bench /lib/firmware /root/firmware'
timeout 120 sshpass -e scp $OPTS \
  "$REPO/scripts/dma_infer_common.py" \
  "$REPO/scripts/slot32_layout.py" \
  "$REPO/scripts/board_fix_hp0_width.py" \
  "$REPO/scripts/board_load_only.sh" \
  "$REPO/scripts/opt_v2/board_10k.py" \
  "$REPO/deploy/dense_head.npz" \
  "$NPZ" \
  root@$IP:/tmp/edgeai_bench/
timeout 20 sshpass -e ssh $OPTS root@$IP 'echo CLOCK; cat /sys/kernel/debug/clk/pl0_ref/clk_rate 2>/dev/null || echo no_pl0'

echo "[$(date '+%F %T')] load known_good"
load_bit "$OLD" "$OLD_MD5"
run_board bench10k_packed.npz 1 v2_old_smoke 60
echo "[$(date '+%F %T')] known_good 10k"
run_board bench10k_packed.npz 10000 v2_old 2400

echo "[$(date '+%F %T')] load RC1"
load_bit "$RC1" "$RC1_MD5"
run_board bench10k_packed.npz 10000 v2_rc1 1800
echo "[$(date '+%F %T')] v2 fetched"
trap - ERR

source ${HOME}/miniconda3/etc/profile.d/conda.sh
conda activate edgeai_39
python3 - <<'PY'
import json
from pathlib import Path
import numpy as np
out = (Path(__import__("os").environ["EDGEAI_ROOT"]) / 'results/opt_v2/v5_v2')
old = np.load(out/"board_gap_v2_old.npy").astype(np.int32)
new = np.load(out/"board_gap_v2_rc1.npy").astype(np.int32)
old_p = np.load(out/"board_pred_v2_old.npy")
new_p = np.load(out/"board_pred_v2_rc1.npy")
old_l = np.load(out/"board_lat_v2_old.npy")
new_l = np.load(out/"board_lat_v2_rc1.npy")
pack = np.load(__import__("os").environ["EDGEAI_ROOT"] + '/results/opt_v2/bench10k_packed.npz')
labels = pack["labels"][:len(old)]
n = min(len(old), len(new), len(labels))
old, new = old[:n], new[:n]
d = np.abs(old-new).max(1)
rng = np.random.default_rng(20261018)
ratio = []
for _ in range(1000):
    idx = rng.integers(0, n, n)
    ratio.append(float(np.median(old_l[idx]) / np.median(new_l[idx])))
ratio = np.sort(np.asarray(ratio))
rep = {
    "n": int(n),
    "timer": "start_transfer to wait_ioc; excludes PS pack and Dense",
    "gap_max_lsb": int(d.max()),
    "gap_n_mismatch": int((d>0).sum()),
    "top1_old": float((old_p[:n]==labels[:n]).mean()),
    "top1_rc1": float((new_p[:n]==labels[:n]).mean()),
    "lat_old_median_ms": float(np.median(old_l[:n])),
    "lat_old_p99_ms": float(np.quantile(old_l[:n], 0.99)),
    "lat_rc1_median_ms": float(np.median(new_l[:n])),
    "lat_rc1_p99_ms": float(np.quantile(new_l[:n], 0.99)),
    "speedup_median_ratio": float(np.median(old_l[:n]) / np.median(new_l[:n])),
    "speedup_bootstrap_p2_5": float(ratio[24]),
    "speedup_bootstrap_p97_5": float(ratio[974]),
}
(out/"v5_v2_compare.json").write_text(json.dumps(rep, indent=1))
print(json.dumps(rep, indent=1))
PY
echo "[$(date '+%F %T')] v2 done"
