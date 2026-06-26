#!/bin/bash
# Strategy step ③: fix C-sim link + run C-sim then Cosim.
set -euo pipefail

REPO="/home/atw/Edge_AI_Acc/claude/EdgeAI-ZU4EV_Claude"
HLS_DIR="${REPO}/notebooks/hls4ml_prj"
VIVADO_HLS="/tools/Xilinx/Vivado/2020.1/bin/vivado_hls"
LOG="${REPO}/results/strategy_csim_cosim.log"

export LIBRARY_PATH="/usr/lib/x86_64-linux-gnu:/lib/x86_64-linux-gnu:${LIBRARY_PATH:-}"
export LD_LIBRARY_PATH="/usr/lib/x86_64-linux-gnu:/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH:-}"

exec > >(tee -a "$LOG") 2>&1
log() { echo "[$(date '+%F %T')] $*"; }

log "=== Strategy ③ HLS C-sim + Cosim ==="
source ~/miniconda3/etc/profile.d/conda.sh
conda activate edgeai_39
cd "$REPO"

python3 scripts/patch_axi_wrapper.py

# Avoid duplicate main: hide legacy myproject_test.cpp during csim/cosim
TEST_CPP="${HLS_DIR}/myproject_test.cpp"
TEST_BAK="${HLS_DIR}/myproject_test.cpp.bak_strategy"
if [[ -f "$TEST_CPP" && ! -f "$TEST_BAK" ]]; then
    mv "$TEST_CPP" "$TEST_BAK"
    log "Moved myproject_test.cpp aside"
fi

# Prepare tb sample0
python3 - <<'PY'
import numpy as np
from pathlib import Path
data = np.load("deploy/cifar10_bench.npz", allow_pickle=True)
raw = bytes(data["payloads"][0])
x = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 1024.0
tb = Path("notebooks/hls4ml_prj/tb_data")
tb.mkdir(parents=True, exist_ok=True)
line = " ".join(str(float(v)) for v in x.flatten())
(tb / "tb_input_features.dat").write_text(line + "\n")
(tb / "tb_output_predictions.dat").write_text(line + "\n")
print("tb_input_features.dat: %d floats" % x.size)
PY

# Clean stale csim objects (duplicate myproject_test.o)
rm -rf "${HLS_DIR}/myproject_prj/solution1/csim/build"

# Patch build_prj.tcl: add linker flags for WSL glibc
python3 - <<'PY'
from pathlib import Path
p = Path("notebooks/hls4ml_prj/build_prj.tcl")
text = p.read_text()
needle = "open_solution\n"
insert = (
    'open_solution\n'
    'config_compile -ldflags "-L/usr/lib/x86_64-linux-gnu -L/lib/x86_64-linux-gnu -lpthread -lm"\n'
)
if 'config_compile -ldflags' not in text:
    text = text.replace(needle, insert, 1)
    p.write_text(text)
    print("Patched build_prj.tcl ldflags")
else:
    print("build_prj.tcl ldflags already present")
PY

cd "$HLS_DIR"

log "--- C-sim ---"
$VIVADO_HLS -f build_prj.tcl reset=0 csim=1 synth=0 cosim=0 validation=0 export=0 || CSIM_RC=$?
CSIM_RC=${CSIM_RC:-0}

RESULT="${HLS_DIR}/tb_data/csim_results.log"
if [[ -f "$RESULT" ]]; then
    log "--- csim_results.log ---"
    cat "$RESULT"
    python3 - <<PY
import json, sys
from pathlib import Path
repo = Path("${REPO}")
line = (repo / "notebooks/hls4ml_prj/tb_data/csim_results.log").read_text().strip().split()
vals = [float(x) for x in line[:10]]
out = {
    "csim_ok": True,
    "output10": [round(v, 4) for v in vals],
    "mid4": [round(v, 4) for v in vals[4:8]],
    "mid4_all_zero": all(abs(v) < 1e-6 for v in vals[4:8]),
}
(repo / "results/strategy_csim_result.json").write_text(json.dumps(out, indent=2))
print(json.dumps(out, indent=2))
PY
else
    log "WARN: csim_results.log missing, rc=$CSIM_RC"
    echo '{"csim_ok": false}' > "${REPO}/results/strategy_csim_result.json"
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
    head -5 "$COSIM_LOG"
fi

[[ -f "$TEST_BAK" ]] && mv "$TEST_BAK" "$TEST_CPP"

log "=== Strategy ③ DONE csim_rc=$CSIM_RC cosim_rc=$COSIM_RC ==="
exit $COSIM_RC
