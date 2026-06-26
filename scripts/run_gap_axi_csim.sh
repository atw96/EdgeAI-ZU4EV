#!/bin/bash
# Exported myproject_axi Vivado csim (GAP 24, slot pack) + board beat alignment.
set -euo pipefail

REPO="/home/atw/Edge_AI_Acc/claude/EdgeAI-ZU4EV_Claude"
HLS_DIR="${REPO}/notebooks/hls4ml_prj"
VIVADO_HLS="/tools/Xilinx/Vivado/2020.1/bin/vivado_hls"
LOG="${REPO}/results/gap_axi_csim_board.log"
BOARD_IP="${BOARD_IP:-192.168.1.40}"
BOARD_PASS="${BOARD_PASS:-root}"
N_GAP_COMPARE="${N_GAP_COMPARE:-10}"

export LIBRARY_PATH="/usr/lib/x86_64-linux-gnu:${LIBRARY_PATH:-}"
export LD_LIBRARY_PATH="/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH:-}"

exec > >(tee -a "$LOG") 2>&1
log() { echo "[$(date '+%F %T')] $*"; }

source ~/miniconda3/etc/profile.d/conda.sh
conda activate edgeai_39
cd "$REPO"

log "=== GAP exported AXI csim + board align (N=$N_GAP_COMPARE) ==="

export OUTPUT_AXIS_BITS=32
export OUTPUT_PACK_MODE=slot
export AXI_DATAFLOW=0
python3 scripts/patch_axi_wrapper.py
python3 scripts/patch_axi_testbench.py
N_GAP_COMPARE="$N_GAP_COMPARE" python3 scripts/prepare_gap_csim_tb.py

# Avoid duplicate main from legacy myproject_test.cpp
TEST_CPP="${HLS_DIR}/myproject_test.cpp"
TEST_BAK="${HLS_DIR}/myproject_test.cpp.bak_gap_csim"
if [[ -f "$TEST_CPP" && ! -f "$TEST_BAK" ]]; then
    mv "$TEST_CPP" "$TEST_BAK"
    log "Moved myproject_test.cpp aside"
fi

# Remove stale ldflags line if a prior attempt added it (unsupported in Vivado 2020.1)
python3 - <<'PY'
from pathlib import Path
p = Path("notebooks/hls4ml_prj/build_prj.tcl")
text = p.read_text()
import re
new = re.sub(r'config_compile -ldflags[^\n]*\n', '', text)
if new != text:
    p.write_text(new)
    print('Removed unsupported config_compile -ldflags from build_prj.tcl')
PY

rm -rf "${HLS_DIR}/myproject_prj/solution1/csim/build"

log "--- Vivado HLS csim (exported hls4ml_prj) ---"
conda deactivate
cd "$HLS_DIR"
$VIVADO_HLS -f build_prj.tcl reset=0 csim=1 synth=0 cosim=0 validation=0 export=0 || CSIM_RC=$?
CSIM_RC=${CSIM_RC:-0}
cd "$REPO"
[[ -f "$TEST_BAK" ]] && mv "$TEST_BAK" "$TEST_CPP"
if [[ "$CSIM_RC" -ne 0 ]]; then
    log "ERROR: csim failed rc=$CSIM_RC"
    exit "$CSIM_RC"
fi

cd "$REPO"
log "--- csim gap sample0 ---"
head -1 "$HLS_DIR/tb_data/csim_results.log" || true
head -1 "$HLS_DIR/tb_data/csim_axis_beats.log" || true

log "--- Deploy board_fetch_gap.py ---"
sshpass -p "$BOARD_PASS" scp -o StrictHostKeyChecking=no \
  scripts/board_fetch_gap.py \
  scripts/dma_infer_common.py \
  scripts/slot32_layout.py \
  deploy/cifar10_bench.npz \
  "root@${BOARD_IP}:/tmp/edgeai_bench/"

log "--- Compare csim vs Keras GAP ---"
source ~/miniconda3/etc/profile.d/conda.sh
conda activate edgeai_39
N_GAP_COMPARE="$N_GAP_COMPARE" python3 scripts/gap_csim_keras_align.py || true

log "--- Compare csim beats vs board ---"
N_GAP_COMPARE="$N_GAP_COMPARE" BOARD_IP="$BOARD_IP" BOARD_PASS="$BOARD_PASS" \
  OUT_DIM=24 OUT_BYTES=92 OUT_FIXED_SCALE=256 \
  python3 scripts/gap_axi_csim_board_align.py

log "=== DONE ==="
