#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
H=${EDGEAI_ROOT}
ls -lh "$H/deploy/cifar10_bench_10k.npz" "$H/deploy/cifar10_bench_1k.npz" 2>/dev/null
python3 - <<'PY'
import re
from pathlib import Path
p = (Path(__import__("os").environ["EDGEAI_ROOT"]) / 'notebooks/hls4ml_prj/firmware/defines.h')
print("defines", p.is_file())
if p.is_file():
    for line in p.read_text(errors="replace").splitlines():
        if "conv1a_accum" in line or "bn_conv1a_scale" in line or "input_t " in line:
            print(line.strip())
t = (Path(__import__("os").environ["EDGEAI_ROOT"]) / 'notebooks/hls4ml_prj/firmware/myproject.cpp').read_text(errors="replace")
print("depth sample", re.findall(r"depth=(\d+)", t)[:8])
PY
ps -ef | grep -E 'vivado|csim' | grep -v grep | head || echo idle
