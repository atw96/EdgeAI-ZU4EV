#!/bin/bash
# hls4ml 1.3 + bit_exact in isolated env; edgeai_39 kept for Vivado HLS/csynth.
set -euo pipefail

REPO="/home/atw/Edge_AI_Acc/claude/EdgeAI-ZU4EV_Claude"
LOG="${REPO}/results/v19_hls4ml_upgrade.log"
HLS4ML_ENV="${HLS4ML_ENV:-edgeai_hls4ml13}"
N_PROFILE="${N_PROFILE:-100}"
N_ACCURACY="${N_ACCURACY:-100}"

exec > >(tee -a "$LOG") 2>&1
log() { echo "[$(date '+%F %T')] $*"; }

LOCK="${REPO}/results/.v19_hls4ml_upgrade.lock"
exec 9>"$LOCK"
if ! flock -n 9; then
  echo "ERROR: another hls4ml upgrade active" >&2
  exit 1
fi

log "=== v19 hls4ml 1.x upgrade (env=$HLS4ML_ENV) ==="
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null || log "WARN: nvidia-smi unavailable"

bash "$REPO/scripts/setup_hls4ml13_env.sh" "$REPO/results/v19_hls4ml13_setup.log"

source ~/miniconda3/etc/profile.d/conda.sh
conda activate "$HLS4ML_ENV"
cd "$REPO"

export OUTPUT_AXIS_BITS=32 OUTPUT_PACK_MODE=slot AXI_DATAFLOW=0
export OUT_DIM=24 OUT_BYTES=92 OUT_LAYOUT=gap_ps OUT_FIXED_SCALE=256
export GAP_ONLY=1

log "--- bit_exact GAP-only convert (hls4ml 1.3) ---"
python3 scripts/v19_bitexact_convert.py
grep -E 'layer27_t|result_t|conv1a' notebooks/hls4ml_prj/firmware/defines.h | head -8 || true

log "--- profiling numerical/compare (Issue #397) ---"
N_PROFILE="$N_PROFILE" python3 scripts/v19_profiling_compare.py 2>&1 | tail -25 || log "WARN: profiling compare partial fail"

log "--- v17 patch chain (same as profiling pipeline) ---"
python3 scripts/patch_hls_rf_v14.py
python3 scripts/patch_hls_restore_dataflow.py
python3 scripts/patch_hls_conv_stream.py || true
python3 scripts/patch_hls_conv_cyclic_restore.py || true
python3 scripts/patch_hls_stream_depth.py
python3 scripts/patch_hls_dense_mult.py
python3 scripts/patch_hls_dense_antihang.py
python3 scripts/patch_hls_dense_resource_antihang.py
python3 scripts/patch_hls_mult_strategy.py
python3 scripts/patch_hls_axi_top.py || true
python3 scripts/patch_axi_wrapper.py
python3 scripts/patch_axi_testbench.py
python3 scripts/patch_hls_axi_csim_tb.py || true

log "--- P0-2 trace ---"
N_TRACE=1 MAE_THRESH=0.05 python3 scripts/v19_p0_layer_trace.py 2>&1 | tail -15

log "--- csim gates (conda still $HLS4ML_ENV for Keras; vivado_hls uses system tool) ---"
N_GAP_COMPARE="$N_ACCURACY" N_ACCURACY="$N_ACCURACY" bash scripts/run_gap_axi_csim.sh 2>&1 | tail -20
python3 scripts/csim_zero_gate.py || true
N_GAP_COMPARE="$N_ACCURACY" python3 scripts/gap_csim_keras_align.py
N_ACCURACY="$N_ACCURACY" OUT_DIM=24 python3 scripts/gap_csim_ps_dense_accuracy.py || true

CSIM_TOP1=$(python3 -c "import json; print(json.load(open('results/gap_csim_ps_dense_accuracy.json'))['csim_ps_dense_top1_pct'])" 2>/dev/null || echo nan)
log "RESULT csim+PS Top-1=${CSIM_TOP1}% (need >=75% before bit rebuild)"

python3 -c "
import json
from pathlib import Path
p = Path('results/v19_hls4ml_upgrade_summary.json')
p.write_text(json.dumps({'hls4ml_env': '$HLS4ML_ENV', 'csim_top1_pct': float('$CSIM_TOP1') if '$CSIM_TOP1' != 'nan' else None}, indent=2))
"

if python3 -c "import json; d=json.load(open('results/v19_hls4ml_upgrade_summary.json')); exit(0 if (d.get('csim_top1_pct') or 0) >= 75 else 1)"; then
  log "csim PASS — run: bash scripts/run_v19_bit_board.sh"
  exit 0
fi

log "csim below 75% — inspect results/v19_p0_layer_trace.md and v19_profiling/"
exit 2
