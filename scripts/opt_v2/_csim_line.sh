#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
H=${EDGEAI_ROOT}
python3 - <<'PY'
from pathlib import Path
p = (Path(__import__("os").environ["EDGEAI_ROOT"]) / 'results/opt_v2/a1_shallow_csim.log')
if not p.is_file():
    p = (Path(__import__("os").environ["EDGEAI_ROOT"]) / 'results/opt_v2/p1_narrow_a1_csim.log')
print("log", p, "lines", sum(1 for _ in p.open()))
print(p.read_text(errors="replace").splitlines()[0][:300])
PY
