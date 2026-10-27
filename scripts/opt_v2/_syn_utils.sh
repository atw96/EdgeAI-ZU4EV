#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
H=${EDGEAI_ROOT}
python3 - <<'PY'
from pathlib import Path
root = (Path(__import__("os").environ["EDGEAI_ROOT"]) / 'notebooks/hls4ml_prj/myproject_prj/solution1/impl')
rpts = list(root.rglob("*util*.rpt"))
print("count", len(rpts))
for p in sorted(rpts, key=lambda x: -x.stat().st_size):
    text = p.read_text(errors="replace")
    lut = bram = dsp = None
    for line in text.splitlines():
        if "CLB LUTs*" in line and "|" in line:
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) > 1 and cells[1].isdigit():
                lut = cells[1]
        if line.strip().startswith("| RAMB") or "Block RAM Tile" in line or "RAMB36" in line or "RAMB18" in line:
            if "Block RAM Tile" in line:
                cells = [c.strip() for c in line.strip("|").split("|")]
                if len(cells) > 1:
                    bram = cells[1]
        if "DSPs" in line and "Available" not in line and "|" in line:
            cells = [c.strip() for c in line.strip("|").split("|")]
            if cells and cells[0] == "DSPs" and len(cells) > 1:
                dsp = cells[1]
    print(f"LUT={lut} BRAM={bram} DSP={dsp} size={p.stat().st_size} {p.relative_to(root)}")
PY
