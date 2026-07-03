#!/bin/bash
# RTL cosim gate: 24-output GAP slot32 AXI testbench (N_GAP_COMPARE samples).
set -euo pipefail

REPO="/home/atw/Edge_AI_Acc/claude/EdgeAI-ZU4EV_Claude"
HLS_DIR="${REPO}/notebooks/hls4ml_prj"
VIVADO_HLS="/tools/Xilinx/Vivado/2020.1/bin/vivado_hls"
LOG="${REPO}/results/hls_csim_cosim.log"
N_GAP_COMPARE="${N_GAP_COMPARE:-2}"

export LIBRARY_PATH="/usr/lib/x86_64-linux-gnu:/lib/x86_64-linux-gnu:${LIBRARY_PATH:-}"
export LD_LIBRARY_PATH="/usr/lib/x86_64-linux-gnu:/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH:-}"
export OUTPUT_AXIS_BITS=32 OUTPUT_PACK_MODE=serial AXI_DATAFLOW=0
export OUT_DIM=24 OUT_BYTES=96 OUT_LAYOUT=gap_ps OUT_FIXED_SCALE=1024
export IN_FIXED_SCALE=1024

exec > >(tee -a "$LOG") 2>&1
log() { echo "[$(date '+%F %T')] $*"; }

log "=== HLS C-sim + RTL Cosim (GAP 24, N=$N_GAP_COMPARE) ==="
source ~/miniconda3/etc/profile.d/conda.sh
conda activate edgeai_39
cd "$REPO"

export HLS_STREAM_DEPTH_PROFILE="${HLS_STREAM_DEPTH_PROFILE:-board_safe}"
python3 scripts/patch_hls_axi_top.py || true
python3 scripts/patch_hls_axi_csim_tb.py || true
python3 scripts/patch_axi_wrapper.py
python3 scripts/patch_axi_testbench.py
N_GAP_COMPARE="$N_GAP_COMPARE" python3 scripts/prepare_gap_csim_tb.py

# Avoid duplicate main from legacy myproject_test.cpp
TEST_CPP="${HLS_DIR}/myproject_test.cpp"
TEST_BAK="${HLS_DIR}/myproject_test.cpp.bak_cosim"
if [[ -f "$TEST_CPP" && ! -f "$TEST_BAK" ]]; then
    mv "$TEST_CPP" "$TEST_BAK"
    log "Moved myproject_test.cpp aside"
fi

# Remove stale ldflags (unsupported in Vivado 2020.1)
python3 - <<'PY'
from pathlib import Path
import re
p = Path("notebooks/hls4ml_prj/build_prj.tcl")
text = p.read_text()
new = re.sub(r'config_compile -ldflags[^\n]*\n', '', text)
if new != text:
    p.write_text(new)
    print('Removed unsupported config_compile -ldflags from build_prj.tcl')
PY

rm -rf "${HLS_DIR}/myproject_prj/solution1/csim/build"

cd "$HLS_DIR"

log "--- C-sim (exported AXI GAP) ---"
$VIVADO_HLS -f build_prj.tcl reset=0 csim=1 synth=0 cosim=0 validation=0 export=0 || CSIM_RC=$?
CSIM_RC=${CSIM_RC:-0}

RESULT="${HLS_DIR}/tb_data/csim_results.log"
if [[ -f "$RESULT" ]]; then
    log "--- csim_results.log (first line, expect 24 floats) ---"
    head -1 "$RESULT"
    python3 - <<PY
import json, sys
from pathlib import Path
repo = Path("${REPO}")
line = (repo / "notebooks/hls4ml_prj/tb_data/csim_results.log").read_text().strip().splitlines()[0].split()
vals = [float(x) for x in line]
out_dim = int("${OUT_DIM}")
out = {
    "csim_ok": len(vals) >= out_dim,
    "out_dim": out_dim,
    "n_values": len(vals),
    "gap_head4": [round(v, 4) for v in vals[:4]],
    "gap_all_zero": all(abs(v) < 1e-6 for v in vals[:out_dim]),
}
(repo / "results/hls_csim_cosim_csim.json").write_text(json.dumps(out, indent=2))
print(json.dumps(out, indent=2))
if not out["csim_ok"] or out["gap_all_zero"]:
    sys.exit(1)
PY
else
    log "WARN: csim_results.log missing, rc=$CSIM_RC"
    echo '{"csim_ok": false}' > "${REPO}/results/hls_csim_cosim_csim.json"
fi

if [[ "$CSIM_RC" -ne 0 ]]; then
    log "C-sim failed (rc=$CSIM_RC); skip cosim"
    [[ -f "$TEST_BAK" ]] && mv "$TEST_BAK" "$TEST_CPP"
    exit "$CSIM_RC"
fi

log "--- RTL Cosim (may take 30-60 min) ---"
$VIVADO_HLS -f build_prj.tcl reset=0 csim=0 synth=0 cosim=1 validation=0 export=0 || COSIM_RC=$?
COSIM_RC=${COSIM_RC:-0}

COSIM_LOG="${HLS_DIR}/tb_data/rtl_cosim_results.log"
if [[ -f "$COSIM_LOG" ]]; then
    log "--- rtl_cosim_results.log ---"
    head -3 "$COSIM_LOG"
fi

python3 - <<PY
import json
from pathlib import Path
repo = Path("${REPO}")
out = {
    "cosim_rc": int("${COSIM_RC:-0}"),
    "cosim_pass": int("${COSIM_RC:-0}") == 0,
    "n_gap_compare": int("${N_GAP_COMPARE}"),
    "rtl_log_exists": (repo / "notebooks/hls4ml_prj/tb_data/rtl_cosim_results.log").is_file(),
}
(repo / "results/hls_csim_cosim.json").write_text(json.dumps(out, indent=2))
print(json.dumps(out, indent=2))
PY

[[ -f "$TEST_BAK" ]] && mv "$TEST_BAK" "$TEST_CPP"

log "=== Cosim gate DONE csim_rc=$CSIM_RC cosim_rc=$COSIM_RC ==="
exit $COSIM_RC
