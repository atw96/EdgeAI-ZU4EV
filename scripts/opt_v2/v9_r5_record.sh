#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
set -uo pipefail
M=${EDGEAI_ROOT}
H=${EDGEAI_ROOT}
cp -f "$M/docs/STATUS.md" "$H/docs/STATUS.md"
python3 - << 'PY'
import json
from pathlib import Path
p = (Path(__import__("os").environ["EDGEAI_ROOT"]) / 'results/opt_v2/v9_fpga.json')
doc = json.loads(p.read_text())
doc["python_149"] = {
    "bit": "rc1",
    "md5": "334e27454dcb05d179d6d188b7d404c3",
    "clock": "0x01010a02",
    "frames": 2000000,
    "holes": 1310260,
    "lsb_bad": 1310262,
    "elapsed_s": 3674.174,
    "latch_1": [55689, 705910],
    "latch_2": [1339962, 1999999],
    "note": "Bytes 64-95 stayed 0xAA. Not a Poisson rate.",
}
doc["python_149_ioc_readback"] = {
    "frames": 600000,
    "holes": 0,
    "length_rejects": 0,
    "tail_rereads": 0,
    "note": "Three back-to-back 200k arms. The first arm only adds IOC readback. Later arms also check length and reread the tail; those counters stayed 0.",
}
p.write_text(json.dumps(doc, indent=2) + "\n")
print("json ok")
PY
# protected bits still the originals
md5sum "$H/deploy/cifar10_accel.bit" "$H/deploy/opt_v2/A1shallow/cifar10_accel.bit" "$H/deploy/release/cifar10_accel.bit"
