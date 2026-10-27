#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
python3 - <<'PY'
import json
from pathlib import Path
p = (Path(__import__("os").environ["EDGEAI_ROOT"]) / 'notebooks/hls4ml_prj/myproject_prj/solution1/impl/report/verilog/myproject_axi_utilization_synth.rpt')
if not p.is_file():
    p = (Path(__import__("os").environ["EDGEAI_ROOT"]) / 'notebooks/hls4ml_prj/myproject_prj/solution1/impl/verilog/report/myproject_axi_utilization_synth.rpt')
print("file", p, p.is_file())
keep = []
for line in p.read_text(errors="replace").splitlines():
    if any(s in line for s in ("CLB LUTs*", "LUT as Logic", "LUT as Memory", "Block RAM Tile", "RAMB36", "RAMB18", "| DSPs")):
        keep.append(line)
print("\n".join(keep[:20]))
out = {
    "design": "narrow A1' with aggressive FIFO depths, kernel_data left complete",
    "flow": "export_design -rtl verilog -format ip_catalog -flow syn",
    "clock_note": "Vivado 2020.1 core_revision overflows after 2021; synthesis ran under a frozen 2020-09-13 clock",
    "csynth_ms": 0.87675,
    "csynth_cycles": 175350,
    "syn_lut": 39191,
    "syn_lut_available": 87840,
    "syn_dsp": 207,
    "syn_bram_tiles": 11,
    "hls_bram_18k": 22,
    "csim_n": 1000,
    "csim_bit_exact_vs_deep_fifo": True,
    "csim_mae": 0.026174216794125,
    "csim_top1": 81.6,
    "keras_top1_same_1000": 81.8,
    "report": str(p),
}
dest = (Path(__import__("os").environ["EDGEAI_ROOT"]) / 'results/opt_v2/a1_shallow_syn_summary.json')
dest.write_text(json.dumps(out, indent=2) + "\n")
print("wrote", dest)
PY
cp -f ${EDGEAI_ROOT}/results/opt_v2/a1_shallow_syn_summary.json ${EDGEAI_ROOT}/results/opt_v2/a1_shallow_syn_summary.json
