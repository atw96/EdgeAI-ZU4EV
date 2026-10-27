#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
H=${EDGEAI_ROOT}
B=$H/notebooks/hls4ml_prj_a2l/myproject_prj/solution1/csim/build
echo "=== build tb ==="
ls -l "$B/tb_data" 2>&1 | head
echo "=== line counts ==="
wc -l "$H/results/opt_v2/v5_synth/tb_input_features.dat" \
  "$H/notebooks/hls4ml_prj_a2l/tb_data/tb_input_features.dat" \
  "$B/tb_data/tb_input_features.dat" 2>&1
echo "=== first line bytes ==="
python3 - << 'PY'
from pathlib import Path
paths = [
__import__("os").environ["EDGEAI_ROOT"] + '/results/opt_v2/v5_synth/tb_input_features.dat',
__import__("os").environ["EDGEAI_ROOT"] + '/notebooks/hls4ml_prj_a2l/tb_data/tb_input_features.dat',
__import__("os").environ["EDGEAI_ROOT"] + '/notebooks/hls4ml_prj_a2l/myproject_prj/solution1/csim/build/tb_data/tb_input_features.dat',
]
for p in paths:
    path = Path(p)
    if not path.exists():
        print("missing", p)
        continue
    with path.open() as f:
        line = f.readline()
    print(path.parent.parent.name if False else path, "line0_chars", len(line), "tokens", len(line.split()))
PY
