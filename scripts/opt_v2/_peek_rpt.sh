#!/bin/bash
python3 - <<'PY'
from pathlib import Path
p = (Path(__import__("os").environ["EDGEAI_ROOT"]) / 'notebooks/hls4ml_prj.bak_bitexact_p1_old_a1csynth/myproject_prj/solution1/syn/report/myproject_axi_csynth.rpt')
lines = p.read_text(errors="replace").splitlines()
for i, line in enumerate(lines):
    if "Latency" in line or "BRAM_18K" in line or "Summary" in line:
        if i < 120 or "Utilization" in line or "BRAM" in line:
            print(f"{i}: {line}")
print("---HEAD---")
print("\n".join(f"{i}: {lines[i]}" for i in range(0, 80)))
PY
