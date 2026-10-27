#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
H=${EDGEAI_ROOT}
python3 - <<'PY'
from pathlib import Path
p = (Path(__import__("os").environ["EDGEAI_ROOT"]) / 'notebooks/hls4ml_prj/myproject_prj/solution1/syn/report/myproject_csynth.rpt')
lines = p.read_text(errors="replace").splitlines()
# print summary util block
for i, line in enumerate(lines):
    if line.strip().startswith("* Summary"):
        print("\n".join(lines[i:i+20]))
        print("----")
        break
rows = []
header = None
in_inst = False
for line in lines:
    if "Instance" in line and "BRAM_18K" in line and "LUT" in line:
        header = [c.strip() for c in line.strip().strip("|").split("|")]
        in_inst = True
        continue
    if not in_inst:
        continue
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    if len(cells) < 2 or set(cells[0]) <= set("+-"):
        continue
    if cells[0] in ("Instance", "Name"):
        continue
    rec = dict(zip(header, cells))
    rows.append(rec)
# keep until a blank-ish end; the table ends at Total or next section
print("nrows", len(rows), "header", header)
def lut_of(r):
    for k, v in r.items():
        if k and "LUT" in k:
            try:
                return int(v.replace(",", ""))
            except ValueError:
                return -1
    return -1
rows.sort(key=lut_of, reverse=True)
for r in rows[:18]:
    name = r.get(header[0], "")[:48]
    mod = r.get(header[1], "")[:40] if len(header) > 1 else ""
    print(f"LUT={lut_of(r):6} {name} | {mod}")
PY
echo ----IMPL----
find "$H/notebooks/hls4ml_prj/myproject_prj/solution1/impl" -name '*.rpt' 2>/dev/null | head
echo ----ERRCTX----
grep -n "export_design\|Starting export\|RTL Synthesis\|synth_design\|ippack\|Failed" "$H/results/opt_v2/logs/a1_shallow_csynth.log" | head -30
