#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
set -euo pipefail
export SSHPASS="${SSHPASS:?SSHPASS}"
OPTS="-o ConnectTimeout=8 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
OUT=${EDGEAI_ROOT}/results/opt_v2/v5_v2
IP=${BOARD_IP:?BOARD_IP}
timeout 20 sshpass -e ssh $OPTS root@$IP 'cat /sys/class/fpga_manager/fpga0/state; ls -l /tmp/edgeai_bench/board_gap_v2_rc1.npy'
timeout 60 sshpass -e ssh $OPTS root@$IP 'cd /tmp/edgeai_bench && tar cf - board_gap_v2_rc1.npy board_pred_v2_rc1.npy board_lat_v2_rc1.npy' | tar xf - -C "$OUT/"
ls -lh "$OUT"/board_*v2_rc1.npy
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
    "date": "2026-10-18",
    "timer": "start_transfer to wait_ioc; excludes PS pack and Dense",
    "clock_hz": 99942389,
    "old_bit_md5": "46987907f8177883048b705fdf68c370",
    "rc1_bit_md5": "334e27454dcb05d179d6d188b7d404c3",
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
    "old_note": "prefix 8400 frames plus tail 1600 after the first SSH ended; same bit, same script, RESET_EACH=1",
}
(out/"v5_v2_compare.json").write_text(json.dumps(rep, indent=1))
print(json.dumps(rep, indent=1))
PY
