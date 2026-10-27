#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
H=${EDGEAI_ROOT}
python3 - <<'PY'
import re
from collections import Counter
from pathlib import Path
p = (Path(__import__("os").environ["EDGEAI_ROOT"]) / 'notebooks/hls4ml_prj/firmware/myproject.cpp')
text = p.read_text(errors="replace")
depths = re.findall(r"depth=(\d+)", text)
print("n", len(depths), "unique", Counter(depths))
PY
echo ----P4MICRO----
grep -n "CSYNTH\|Error\|ERROR\|done" "$H/results/opt_v2/logs/p4_micro_csynth.log" | head -30
ps -ef | grep p4_micro_csynth | grep -v grep | awk '{print $2,$8}' || echo p4_done
