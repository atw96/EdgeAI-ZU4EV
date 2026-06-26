#!/bin/bash
# Run Vivado HLS C-simulation on myproject_axi (RTL C++ path, not hls4ml Python).
set -euo pipefail

REPO="/home/atw/Edge_AI_Acc/claude/EdgeAI-ZU4EV_Claude"
HLS_DIR="${REPO}/notebooks/hls4ml_prj"
VIVADO_HLS="/tools/Xilinx/Vivado/2020.1/bin/vivado_hls"
LOG="${REPO}/results/hls_axi_csim.log"

exec > >(tee "$LOG") 2>&1
log() { echo "[$(date '+%F %T')] $*"; }

log "=== HLS AXI C-sim ==="
source ~/miniconda3/etc/profile.d/conda.sh
conda activate edgeai_39
cd "$REPO"

python3 scripts/patch_axi_wrapper.py

# Feed sample0 float image into tb (myproject_axi_test uses float lines)
python3 - <<'PY'
import numpy as np
from pathlib import Path
npz = Path("deploy/cifar10_bench.npz")
data = np.load(npz, allow_pickle=True)
raw = bytes(data["payloads"][0])
x = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 1024.0
tb = Path("notebooks/hls4ml_prj/tb_data")
tb.mkdir(parents=True, exist_ok=True)
line = " ".join(str(float(v)) for v in x.flatten())
(tb / "tb_input_features.dat").write_text(line + "\n", encoding="utf-8")
# placeholder predictions line (csim ignores if using zero fallback)
(tb / "tb_output_predictions.dat").write_text(line + "\n", encoding="utf-8")
print("Wrote tb_input_features.dat (%d floats)" % x.size)
PY

cd "$HLS_DIR"
$VIVADO_HLS -f build_prj.tcl reset=0 csim=1 synth=0 cosim=0 validation=0 export=0

CSIM_LOG="${HLS_DIR}/myproject_prj/solution1/csim/report/myproject_axi_csim.log"
if [[ -f "$CSIM_LOG" ]]; then
    log "--- csim log tail ---"
    tail -30 "$CSIM_LOG"
fi
RESULT="${HLS_DIR}/tb_data/csim_results.log"
if [[ -f "$RESULT" ]]; then
    log "--- csim_results.log ---"
    cat "$RESULT"
fi
log "=== HLS AXI C-sim DONE ==="
