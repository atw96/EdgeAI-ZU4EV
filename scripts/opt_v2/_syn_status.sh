#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
H=${EDGEAI_ROOT}
ps -ef | grep -E 'a1_shallow_syn|vivado' | grep -v grep | awk '{print $2,$8,$9,$10}' || echo none
echo ----TAIL----
tail -n 12 "$H/results/opt_v2/logs/a1_shallow_syn.log" 2>/dev/null || echo no
echo ----JSON----
python3 - <<'PY'
import json
from pathlib import Path
p = (Path(__import__("os").environ["EDGEAI_ROOT"]) / 'results/opt_v2/a1_shallow_syn.json')
print("exists", p.is_file(), "size", p.stat().st_size if p.is_file() else 0)
if p.is_file():
    d = json.loads(p.read_text())
    print("nrpt", len(d.get("rpts", [])))
    print(d.get("util_excerpt", "")[:1500])
PY
