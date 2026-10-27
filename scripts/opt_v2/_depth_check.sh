#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
H=${EDGEAI_ROOT}
grep -n "stream depth\|depths\|profile" "$H/results/opt_v2/logs/a1_shallow_outer.log" | head -20
echo ----CPP----
python3 - <<'PY'
import re
from collections import Counter
from pathlib import Path
t = (Path(__import__("os").environ["EDGEAI_ROOT"]) / 'notebooks/hls4ml_prj/firmware/myproject.cpp').read_text()
print(Counter(re.findall(r"depth=(\d+)", t)))
PY
