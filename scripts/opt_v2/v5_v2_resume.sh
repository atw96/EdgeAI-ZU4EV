#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
# Finish the known_good 10k from the saved prefix, then measure RC1.
# Target: wsl-local SSH to ${BOARD_IP:?BOARD_IP}. One session. No DMA unless operating.
set -euo pipefail
set -o errtrace
REPO=${EDGEAI_ROOT}
IP=${BOARD_IP:?BOARD_IP}
OUT=$REPO/results/opt_v2/v5_v2
RC1=$REPO/deploy/opt_v2/A1shallow/cifar10_accel.bit
RC1_MD5=334e27454dcb05d179d6d188b7d404c3
export SSHPASS="${SSHPASS:?SSHPASS}"
OPTS="-o ConnectTimeout=8 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ServerAliveInterval=15 -o ServerAliveCountMax=80"
LOG=$REPO/results/opt_v2/logs/v5_v2_resume.log
mkdir -p "$OUT" "$REPO/results/opt_v2/logs"
exec > >(tee -a "$LOG") 2>&1
echo "[$(date '+%F %T')] v2 resume"

restore_rc1() {
  echo "[$(date '+%F %T')] restore RC1 after error"
  timeout 60 sshpass -e scp $OPTS "$RC1" root@$IP:/tmp/edgeai_bench/cifar10_accel.bit || true
  timeout 80 sshpass -e ssh $OPTS root@$IP 'cp -f /tmp/edgeai_bench/cifar10_accel.bit /lib/firmware/cifar10_accel.bit; cp -f /tmp/edgeai_bench/cifar10_accel.bit /root/firmware/cifar10_accel.bit; cd /tmp/edgeai_bench && FORCE_PL_RELOAD=1 sh board_load_only.sh' || true
}
trap restore_rc1 ERR

timeout 20 sshpass -e ssh $OPTS root@$IP 'cat /sys/class/fpga_manager/fpga0/state; ps | grep python | grep -v grep || echo no_python'
timeout 40 sshpass -e ssh $OPTS root@$IP 'cd /tmp/edgeai_bench && tar cf - board_gap_v2_old.npy board_pred_v2_old.npy board_lat_v2_old.npy' | tar xf - -C "$OUT/"

source ${HOME}/miniconda3/etc/profile.d/conda.sh
conda activate edgeai_39
python3 - <<'PY'
import numpy as np
from pathlib import Path
repo = Path(__import__("os").environ["EDGEAI_ROOT"])
out = repo / "results/opt_v2/v5_v2"
gap = np.load(out / "board_gap_v2_old.npy")
print("prefix", gap.shape, gap.dtype)
n0 = int(gap.shape[0])
if n0 >= 10000:
    raise SystemExit(0)
pack = np.load(repo / "results/opt_v2/bench10k_packed.npz")
np.savez(out / "v2_old_tail.npz", payloads=pack["payloads"][n0:], labels=pack["labels"][n0:])
Path(out / "v2_prefix_n.txt").write_text(str(n0))
print("tail", 10000 - n0)
PY

N0=$(cat "$OUT/v2_prefix_n.txt")
if [ "$N0" -lt 10000 ]; then
  TAIL=$((10000 - N0))
  timeout 40 sshpass -e scp $OPTS "$OUT/v2_old_tail.npz" "$REPO/scripts/opt_v2/board_10k.py" root@$IP:/tmp/edgeai_bench/
  STATE=$(timeout 15 sshpass -e ssh $OPTS root@$IP 'cat /sys/class/fpga_manager/fpga0/state')
  echo "state before tail [$STATE]"
  test "$STATE" = "operating"
  timeout 20 sshpass -e ssh $OPTS root@$IP 'cd /tmp/edgeai_bench && python3 board_fix_hp0_width.py'
  echo "[$(date '+%F %T')] tail $TAIL"
  timeout 1800 sshpass -e ssh $OPTS root@$IP "cd /tmp/edgeai_bench && export OUT_DIM=24 OUT_BYTES=96 OUT_LAYOUT=gap_ps OUT_FIXED_SCALE=1024 OUTPUT_PACK_MODE=serial DMA_IOC_TIMEOUT_S=8 PYTHONUNBUFFERED=1 BENCH_NPZ=/tmp/edgeai_bench/v2_old_tail.npz N_BOARD=${TAIL} RESET_EACH=1 BOARD_TAG=v2_old_tail && python3 board_10k.py"
  timeout 40 sshpass -e ssh $OPTS root@$IP 'cd /tmp/edgeai_bench && tar cf - board_gap_v2_old_tail.npy board_pred_v2_old_tail.npy board_lat_v2_old_tail.npy' | tar xf - -C "$OUT/"
  python3 - <<'PY'
import numpy as np
from pathlib import Path
out = (Path(__import__("os").environ["EDGEAI_ROOT"]) / 'results/opt_v2/v5_v2')
n0 = int((out / "v2_prefix_n.txt").read_text())
for kind in ("gap", "pred", "lat"):
    a = np.load(out / f"board_{kind}_v2_old.npy")
    b = np.load(out / f"board_{kind}_v2_old_tail.npy")
    c = np.concatenate([a[:n0], b], axis=0)
    assert c.shape[0] == 10000, (kind, a.shape, b.shape, n0)
    np.save(out / f"board_{kind}_v2_old.npy", c)
    print(kind, c.shape)
PY
fi

echo "[$(date '+%F %T')] load RC1"
timeout 80 sshpass -e scp $OPTS "$RC1" "$REPO/scripts/board_load_only.sh" "$REPO/scripts/board_fix_hp0_width.py" "$REPO/scripts/dma_infer_common.py" "$REPO/scripts/slot32_layout.py" "$REPO/results/opt_v2/bench10k_packed.npz" root@$IP:/tmp/edgeai_bench/
timeout 80 sshpass -e ssh $OPTS root@$IP 'cp -f /tmp/edgeai_bench/cifar10_accel.bit /lib/firmware/cifar10_accel.bit; cp -f /tmp/edgeai_bench/cifar10_accel.bit /root/firmware/cifar10_accel.bit; cd /tmp/edgeai_bench && FORCE_PL_RELOAD=1 sh board_load_only.sh'
GOT=$(timeout 15 sshpass -e ssh $OPTS root@$IP 'md5sum /lib/firmware/cifar10_accel.bit' | awk '{print $1}')
STATE=$(timeout 15 sshpass -e ssh $OPTS root@$IP 'cat /sys/class/fpga_manager/fpga0/state')
echo "rc1 md5 $GOT state $STATE"
test "$GOT" = "$RC1_MD5"
test "$STATE" = "operating"
timeout 20 sshpass -e ssh $OPTS root@$IP 'cd /tmp/edgeai_bench && python3 board_fix_hp0_width.py'
echo "[$(date '+%F %T')] RC1 10k"
timeout 1800 sshpass -e ssh $OPTS root@$IP 'cd /tmp/edgeai_bench && export OUT_DIM=24 OUT_BYTES=96 OUT_LAYOUT=gap_ps OUT_FIXED_SCALE=1024 OUTPUT_PACK_MODE=serial DMA_IOC_TIMEOUT_S=8 PYTHONUNBUFFERED=1 BENCH_NPZ=/tmp/edgeai_bench/bench10k_packed.npz N_BOARD=10000 RESET_EACH=1 BOARD_TAG=v2_rc1 && python3 board_10k.py'
timeout 60 sshpass -e ssh $OPTS root@$IP 'cd /tmp/edgeai_bench && tar cf - board_gap_v2_rc1.npy board_pred_v2_rc1.npy board_lat_v2_rc1.npy' | tar xf - -C "$OUT/"
trap - ERR

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
labels = np.load(__import__("os").environ["EDGEAI_ROOT"] + '/results/opt_v2/bench10k_packed.npz')["labels"]
n = min(len(old), len(new), len(labels), len(old_l), len(new_l))
d = np.abs(old[:n] - new[:n]).max(1)
rng = np.random.default_rng(20261018)
ratio = np.empty(1000)
for i in range(1000):
    idx = rng.integers(0, n, n)
    ratio[i] = np.median(old_l[idx]) / np.median(new_l[idx])
ratio.sort()
rep = {
    "n": int(n),
    "timer": "start_transfer to wait_ioc; excludes PS pack and Dense",
    "clock_note": "pl0_ref measured 99942389 Hz on this boot",
    "gap_max_lsb": int(d.max()),
    "gap_n_mismatch": int((d > 0).sum()),
    "top1_old": float((old_p[:n] == labels[:n]).mean()),
    "top1_rc1": float((new_p[:n] == labels[:n]).mean()),
    "lat_old_median_ms": float(np.median(old_l[:n])),
    "lat_old_p99_ms": float(np.quantile(old_l[:n], 0.99)),
    "lat_rc1_median_ms": float(np.median(new_l[:n])),
    "lat_rc1_p99_ms": float(np.quantile(new_l[:n], 0.99)),
    "speedup_median_ratio": float(np.median(old_l[:n]) / np.median(new_l[:n])),
    "speedup_bootstrap_p2_5": float(ratio[24]),
    "speedup_bootstrap_p97_5": float(ratio[974]),
    "old_prefix_frames_before_resume": int((Path(__import__("os").environ["EDGEAI_ROOT"]) / 'results/opt_v2/v5_v2/v2_prefix_n.txt').read_text()) if (Path(__import__("os").environ["EDGEAI_ROOT"]) / 'results/opt_v2/v5_v2/v2_prefix_n.txt').exists() else 10000,
}
(out/"v5_v2_compare.json").write_text(json.dumps(rep, indent=1))
print(json.dumps(rep, indent=1))
PY
echo "[$(date '+%F %T')] v2 resume done"
