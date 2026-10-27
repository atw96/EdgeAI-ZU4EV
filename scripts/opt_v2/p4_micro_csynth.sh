#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
# Csynth the eight P4 micro projects and record achieved II.
# Target host: wsl-local. Caller must ensure Vivado is free.
set -euo pipefail
REPO=${EDGEAI_ROOT}
ROOT="$REPO/results/opt_v2/p4_micro"
OUT="$REPO/results/opt_v2/p4_micro_csynth.json"
LOG="$REPO/results/opt_v2/logs/p4_micro_csynth.log"
if [[ -f "$OUT" ]]; then
  echo "refuse overwrite $OUT" >&2
  exit 2
fi
exec > >(tee -a "$LOG") 2>&1
echo "[$(date '+%F %T')] P4 micro csynth"
source /tools/Xilinx/Vivado/2020.1/settings64.sh
python3 - <<'PY'
import json, re, subprocess
from pathlib import Path
repo = Path(__import__("os").environ["EDGEAI_ROOT"])
root = repo / "results/opt_v2/p4_micro"
hls = "/tools/Xilinx/Vivado/2020.1/bin/vivado_hls"
rows = []
for prj in sorted(p for p in root.iterdir() if (p / "build_prj.tcl").is_file()):
    print("CSYNTH", prj.name, flush=True)
    subprocess.check_call(
        [hls, "-f", "build_prj.tcl", "reset=1", "csim=0", "synth=1", "cosim=0", "validation=0", "export=0"],
        cwd=str(prj),
    )
    log = (prj / "vivado_hls.log").read_text(errors="replace")
    iis = [int(x) for x in re.findall(r"Final II = (\d+)", log)]
    rpt_dir = prj / "myproject_prj/solution1/syn/report"
    top = next(rpt_dir.glob("myproject_csynth.rpt"))
    text = top.read_text(errors="replace")
    lat = None
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if "Latency (cycles)" not in line:
            continue
        for nxt in lines[i+1:i+8]:
            if "ms" not in nxt and "us" not in nxt and "ns" not in nxt:
                continue
            cells = [c.strip() for c in nxt.strip().strip("|").split("|")]
            nums = [int(c.replace(",", "")) for c in cells if re.fullmatch(r"[\d,]+", c)]
            if len(nums) >= 2:
                lat = nums[1]
                break
        if lat:
            break
    util = {}
    for line in lines:
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if cells and cells[0] == "Total" and len(cells) >= 5:
            for k, c in zip(("BRAM_18K", "DSP48E", "FF", "LUT"), cells[1:5]):
                if re.fullmatch(r"[\d,]+", c):
                    util[k] = int(c.replace(",", ""))
            break
    # theory: 32*32*RF for a same-padded 32x32 conv, if the spatial loop is 1024
    m = re.search(r"rf(\d+)", prj.name)
    rf = int(m.group(1)) if m else None
    row = {
        "name": prj.name,
        "rf": rf,
        "patched": prj.name.endswith("_patched"),
        "top_latency_cycles_max": lat,
        "csynth_ms": None if lat is None else lat * 5.0 / 1e6,
        "theory_cycles_1024_times_rf": None if rf is None else 1024 * rf,
        "final_ii": iis,
        "final_ii_max": max(iis) if iis else None,
        "util": util,
    }
    print(json.dumps(row), flush=True)
    rows.append(row)
out = {
    "clock_ns": 5.0,
    "note": "stock is hls4ml 1.3 as generated; patched applies conv_stream cyclic factor 4",
    "cases": rows,
}
path = repo / "results/opt_v2/p4_micro_csynth.json"
path.write_text(json.dumps(out, indent=2) + "\n")
print("wrote", path)
PY
echo "[$(date '+%F %T')] P4 micro csynth done"
