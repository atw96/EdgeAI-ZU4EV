#!/bin/bash
# v19: csynth + Vivado bit + board N=100 (profiling-adjusted conv precision).
set -euo pipefail

REPO="/home/atw/Edge_AI_Acc/claude/EdgeAI-ZU4EV_Claude"
LOG="${REPO}/results/v19_bit_board.log"
HLS="${REPO}/notebooks/hls4ml_prj"
VIVADO_HLS="/tools/Xilinx/Vivado/2020.1/bin/vivado_hls"
N_ACCURACY="${N_ACCURACY:-100}"
MIN_TOP1="${MIN_TOP1:-75}"

exec > >(tee -a "$LOG") 2>&1
log() { echo "[$(date '+%F %T')] $*"; }

LOCK="${REPO}/results/.v19_bit_board.lock"
exec 9>"$LOCK"
if ! flock -n 9; then
  echo "ERROR: another v19 bit build active" >&2
  exit 1
fi

source ~/miniconda3/etc/profile.d/conda.sh
conda activate edgeai_39
cd "$REPO"

export OUTPUT_AXIS_BITS=32 OUTPUT_PACK_MODE=slot AXI_DATAFLOW=0
export OUT_DIM=24 OUT_BYTES=92 OUT_LAYOUT=gap_ps OUT_FIXED_SCALE=256
export GATE_WARN_ONLY=1
export DENSE_MULT_PARTITION_FACTOR=16
export HLS_KERNEL_CYCLIC_FACTOR=4 HLS_RES_CYCLIC_FACTOR=4

OLD=$(md5sum deploy/cifar10_accel.bit 2>/dev/null | awk '{print $1}')
log "=== v19 bit+board (old MD5=$OLD) ==="

log "--- re-patch AXI 32-bit slot (fix profiling default 16-bit pair) ---"
python3 scripts/patch_hls_stream_depth.py
python3 scripts/patch_hls_axi_top.py || true
python3 scripts/patch_axi_wrapper.py
python3 scripts/patch_axi_testbench.py
python3 scripts/patch_hls_axi_csim_tb.py || true
grep -E 'axis_out|pack=|OUTPUT_AXIS' "${HLS}/firmware/myproject_axi.cpp" | head -5 || true

log "--- quick csim sanity (N=3) ---"
N_GAP_COMPARE=3 N_ACCURACY=3 bash scripts/run_gap_axi_csim.sh 2>&1 | tail -8
head -1 "${HLS}/tb_data/csim_results.log" || true

log "--- HLS csynth + export ---"
export LIBRARY_PATH="/usr/lib/x86_64-linux-gnu:${LIBRARY_PATH:-}"
conda deactivate
cd "$HLS"
rm -rf myproject_prj/solution1/.autopilot \
       myproject_prj/solution1/syn \
       myproject_prj/solution1/csim 2>/dev/null || true
$VIVADO_HLS -f build_prj.tcl reset=1 csim=0 synth=1 cosim=0 validation=0 export=0
$VIVADO_HLS -f build_prj.tcl reset=0 csim=0 synth=0 cosim=0 validation=0 export=1
cd "$REPO"
conda activate edgeai_39
python3 scripts/hls_csynth_gate.py || log "WARN: csynth resource gate"

log "--- Vivado rebuild (~45-60 min) ---"
source /tools/Xilinx/Vivado/2020.1/settings64.sh
export FORCE_REBUILD=1 HLS_OUTPUT_AXIS_BITS=32
rm -rf vivado_project/.cache/ip 2>/dev/null || true
bash scripts/rebuild_bitstream.sh --no-sync

NEW=$(md5sum deploy/cifar10_accel.bit | awk '{print $1}')
log "New bit MD5=$NEW (was $OLD)"

log "--- board deploy + benchmark N=$N_ACCURACY ---"
ssh-keygen -f "$HOME/.ssh/known_hosts" -R "${BOARD_IP:-192.168.1.40}" 2>/dev/null || true
OUT_DIM=24 OUT_BYTES=92 OUT_LAYOUT=gap_ps OUT_FIXED_SCALE=256 \
  BOARD_IP="${BOARD_IP:-192.168.1.40}" BOARD_PASS="${BOARD_PASS:-root}" \
  bash scripts/board_auto_fix.sh 2>&1 | tee "${REPO}/results/v19_board_bench.log"

conda activate edgeai_39
N_ACCURACY="$N_ACCURACY" OUT_DIM=24 python3 scripts/gap_csim_ps_dense_accuracy.py || true

BOARD_TOP1=$(python3 -c "import json; print(json.load(open('results/gap_csim_ps_dense_accuracy.json'))['board_top1_pct'])" 2>/dev/null || echo nan)
CSIM_TOP1=$(python3 -c "import json; print(json.load(open('results/gap_csim_ps_dense_accuracy.json'))['csim_ps_dense_top1_pct'])" 2>/dev/null || echo nan)
log "RESULT: csim Top-1=${CSIM_TOP1}% board Top-1=${BOARD_TOP1}% (target ${MIN_TOP1}%)"

python3 -c "
import json
from pathlib import Path
p = Path('results/v19_bit_board_summary.json')
p.write_text(json.dumps({
    'old_bit_md5': '$OLD',
    'new_bit_md5': '$NEW',
    'csim_top1_pct': float('$CSIM_TOP1') if '$CSIM_TOP1' != 'nan' else None,
    'board_top1_pct': float('$BOARD_TOP1') if '$BOARD_TOP1' != 'nan' else None,
    'min_top1_required': $MIN_TOP1,
    'pass': float('$BOARD_TOP1') >= $MIN_TOP1 if '$BOARD_TOP1' != 'nan' else False,
}, indent=2))
print('written', p)
"

if python3 -c "import json; d=json.load(open('results/v19_bit_board_summary.json')); exit(0 if d.get('pass') else 1)"; then
  log "=== v19 bit+board PASS (Top-1 >= ${MIN_TOP1}%) ==="
  exit 0
fi

log "=== v19 bit+board: Top-1 below ${MIN_TOP1}% — schedule hls4ml upgrade ==="
exit 2
