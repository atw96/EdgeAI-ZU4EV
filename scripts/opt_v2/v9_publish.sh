#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
set -uo pipefail
H=${EDGEAI_ROOT}
M=${EDGEAI_ROOT}
mkdir -p "$H/deploy/release" "$M/deploy/release"
cp -f "$H/results/opt_v2/a2l/cifar10_accel.bit" "$H/deploy/release/cifar10_accel.bit"
if [ -f "$H/results/opt_v2/a2l/cifar10_accel.hwh" ]; then
  cp -f "$H/results/opt_v2/a2l/cifar10_accel.hwh" "$H/deploy/release/cifar10_accel.hwh"
fi
cp -f "$H/deploy/dense_head.npz" "$H/deploy/release/dense_head.npz"
{
  echo "RC2 recommended point. Default scripts were not retargeted."
  echo "known_good deploy/cifar10_accel.bit remains 46987907f8177883048b705fdf68c370"
  echo "RC1 deploy/opt_v2/A1shallow/cifar10_accel.bit remains 334e27454dcb05d179d6d188b7d404c3"
  md5sum "$H/deploy/release/cifar10_accel.bit" "$H/deploy/release/cifar10_accel.hwh" "$H/deploy/release/dense_head.npz" 2>/dev/null
  md5sum "$H/deploy/cifar10_accel.bit" "$H/deploy/opt_v2/A1shallow/cifar10_accel.bit"
} > "$H/deploy/release/MD5LIST.txt"
cp -f "$H/deploy/release/cifar10_accel.bit" "$M/deploy/release/cifar10_accel.bit"
cp -f "$H/deploy/release/MD5LIST.txt" "$M/deploy/release/MD5LIST.txt"
if [ -f "$H/deploy/release/cifar10_accel.hwh" ]; then
  cp -f "$H/deploy/release/cifar10_accel.hwh" "$M/deploy/release/cifar10_accel.hwh"
fi
cp -f "$M/docs/STATUS.md" "$H/docs/STATUS.md"
echo "---- md5 list ----"
cat "$H/deploy/release/MD5LIST.txt"
python3 - << 'PY'
import json
from pathlib import Path
p = (Path(__import__("os").environ["EDGEAI_ROOT"]) / 'results/opt_v2/v9_fpga.json')
doc = json.loads(p.read_text())
doc["cpu_tflite"] = {
    "backend": "tflite_runtime 2.5.0.post1 cp37 aarch64",
    "threads_1": {"top1": 0.7933, "invoke_ms": [13.8567, 13.8726, 13.8581], "e2e_ms": [14.0230, 14.0512, 14.0325]},
    "threads_4": {"top1": 0.7933, "invoke_ms": [12.1853, 12.1917, 12.1802], "e2e_ms": [12.3762, 12.3826, 12.3703]},
    "input": "int8 scale 1/255 zero_point -128",
    "note": "Same 10k payloads. Accuracy is not the FPGA model's 81.78%.",
}
doc["ab_c_harness_10k_x3"]["cpu_e2e_1thread_over_rc2_149_hot"] = round(14.0325 / 0.3972, 2)
doc["ab_c_harness_10k_x3"]["cpu_e2e_4thread_over_rc2_149_hot"] = round(12.3762 / 0.3972, 2)
p.write_text(json.dumps(doc, indent=2) + "\n")
print("json updated")
PY
# known_good must be unchanged
python3 - << 'PY'
import hashlib
from pathlib import Path
H = Path(__import__("os").environ["EDGEAI_ROOT"])
def md5(p):
    h = hashlib.md5()
    h.update(p.read_bytes())
    return h.hexdigest()
checks = {
    H / "deploy/cifar10_accel.bit": "46987907f8177883048b705fdf68c370",
    H / "deploy/opt_v2/A1shallow/cifar10_accel.bit": "334e27454dcb05d179d6d188b7d404c3",
    H / "deploy/release/cifar10_accel.bit": "395160123c39a98d478e598c9f93e39e",
}
for path, expect in checks.items():
    got = md5(path)
    print(("OK" if got == expect else "MISMATCH"), path.name, got)
PY
