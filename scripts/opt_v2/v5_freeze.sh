#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
# V0: freeze RC1 hashes. Does not rebuild and does not touch the board.
set -euo pipefail
H=${EDGEAI_ROOT}
OUT=$H/results/opt_v2/v5_rc1_freeze
mkdir -p "$OUT"
cd "$H"
python3 - <<'PY'
import hashlib, json, os
from pathlib import Path
H = Path(__import__("os").environ["EDGEAI_ROOT"])
out = H / "results/opt_v2/v5_rc1_freeze"

def md5(p):
    h = hashlib.md5()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

def pick(*cands):
    for c in cands:
        if c.is_file():
            return c
    return None

files = {
    "rc1_bit": H / "deploy/opt_v2/A1shallow/cifar10_accel.bit",
    "rc1_hwh": H / "deploy/opt_v2/A1shallow/cifar10_accel.hwh",
    "known_good_bit": H / "deploy/cifar10_accel.bit",
    "known_good_hwh": H / "deploy/cifar10_accel.hwh",
    "defines": H / "notebooks/hls4ml_prj/firmware/defines.h",
    "parameters": H / "notebooks/hls4ml_prj/firmware/parameters.h",
    "q6_h5": H / "notebooks/model_int8_qkeras.h5",
    "dense_head": H / "deploy/dense_head.npz",
}
# weight headers
wdir = H / "notebooks/hls4ml_prj/firmware/weights"
weights = {}
if wdir.is_dir():
    for p in sorted(wdir.glob("*.h")):
        weights[p.name] = md5(p)
manifest = {
    "id": "RC1",
    "date": "2026-10-18",
    "bit_path": "deploy/opt_v2/A1shallow/cifar10_accel.bit",
    "patches": [
        "kernel_data left as hls4ml complete (cyclic factor 4 removed)",
        "aggressive FIFO depth",
        "BIT_EXACT=0 narrow ap_fixed<16,8,AP_RND_CONV,AP_SAT>",
        "RF A1' 27/144/144/180/180/216",
    ],
    "env": {
        "hls4ml": "1.3.0",
        "vivado": "2020.1",
        "vivado_hls": "2020.1",
    },
    "git": "workspace is not a git repo",
    "files": {},
    "weights": weights,
    "not_done": ["power", "cpu tflite 10k remeasure", "black-frame board!=csim"],
}
for k, p in files.items():
    if p.is_file():
        manifest["files"][k] = {"path": str(p.relative_to(H)), "md5": md5(p), "bytes": p.stat().st_size}
    else:
        manifest["files"][k] = {"path": str(p), "missing": True}
(out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
print(json.dumps(manifest["files"], indent=2))
print("weights", len(weights))
PY
# known_good copies, do not rename the live deploy bit
mkdir -p "$H/deploy/opt_v2/known_good"
cp -n "$H/deploy/cifar10_accel.bit" "$H/deploy/opt_v2/known_good/known_good_cifar10_accel.bit" || true
cp -n "$H/deploy/cifar10_accel.hwh" "$H/deploy/opt_v2/known_good/known_good_cifar10_accel.hwh" || true
echo FREEZE_DONE
