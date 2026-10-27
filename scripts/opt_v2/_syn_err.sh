#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
H=${EDGEAI_ROOT}
python3 - <<'PY'
from pathlib import Path
p = (Path(__import__("os").environ["EDGEAI_ROOT"]) / 'results/opt_v2/logs/a1_shallow_csynth.log')
lines = p.read_text(errors="replace").splitlines()
print("nlines", len(lines))
for i in range(4065, min(len(lines), 4125)):
    print(f"{i}: {lines[i]}")
PY
echo ----VERILOG----
ls "$H/notebooks/hls4ml_prj/myproject_prj/solution1/impl" 2>/dev/null | head || echo no_impl
ls "$H/notebooks/hls4ml_prj/myproject_prj/solution1/syn/verilog" 2>/dev/null | head || echo no_v
