#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
H=${EDGEAI_ROOT}
python3 - <<'PY'
from pathlib import Path
for label, p in [
    ("P4", (Path(__import__("os").environ["EDGEAI_ROOT"]) / 'notebooks/hls4ml_prj.bak_bitexact_p1_narrow_p4/myproject_prj/solution1/syn/report/myproject_axi_csynth.rpt')),
    ("A1", (Path(__import__("os").environ["EDGEAI_ROOT"]) / 'notebooks/hls4ml_prj/myproject_prj/solution1/syn/report/myproject_axi_csynth.rpt')),
]:
    lines = p.read_text(errors="replace").splitlines()
    print("====", label)
    print("\n".join(lines[25:45]))
PY
echo ----ATTR----
python3 "$H/scripts/opt_v2/p2_attribution.py" \
  --report-dir "$H/notebooks/hls4ml_prj/myproject_prj/solution1/syn/report" \
  --log "$H/results/opt_v2/logs/a1_narrow_csynth.log" \
  --out "$H/results/opt_v2/a1_narrow_attribution.json" || echo attr_fail
python3 - <<'PY'
import json
from pathlib import Path
p = (Path(__import__("os").environ["EDGEAI_ROOT"]) / 'results/opt_v2/a1_narrow_attribution.json')
if not p.is_file():
    raise SystemExit("no attr")
d = json.loads(p.read_text())
print("keys", sorted(d.keys()))
fifo = d.get("fifo") or d.get("fifos") or {}
print("fifo", json.dumps(fifo)[:2000])
print("verdict", d.get("verdict"))
# print bram groups if present
for k in ("fifo_groups", "bram_by_group", "conv1a"):
    if k in d:
        print(k, json.dumps(d[k])[:1500])
PY
echo ----P4LOG----
grep -n "CSYNTH\|wrote\|final_ii\|Error\|ERROR" "$H/results/opt_v2/logs/p4_micro_csynth.log" | head -40
