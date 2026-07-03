#!/bin/bash
# Route 1 fallback: alpha=1 QAT retrain -> BIT_EXACT convert -> csim gates
set -euo pipefail

REPO="/home/atw/Edge_AI_Acc/claude/EdgeAI-ZU4EV_Claude"
LOG="${REPO}/results/v19_alpha1_fallback.log"
FT_EPOCHS="${FT_EPOCHS:-40}"

exec > >(tee -a "$LOG") 2>&1
log() { echo "[$(date '+%F %T')] [alpha1] $*"; }

source ~/miniconda3/etc/profile.d/conda.sh
cd "$REPO"

export PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python
export QAT_ALPHA=1
export BIT_EXACT=1
export OUTPUT_AXIS_BITS=32 OUTPUT_PACK_MODE=slot AXI_DATAFLOW=0
export OUT_DIM=24 OUT_BYTES=92 OUT_LAYOUT=gap_ps OUT_FIXED_SCALE=256 GAP_ONLY=1
export SKIP_BOARD=1 N_ACCURACY=100 CSIM_TOP1_MIN=75

log "=== alpha=1 finetune (${FT_EPOCHS} epochs) ==="
conda activate edgeai_39
bash scripts/ensure_edgeai39_protobuf.sh
FT_EPOCHS="$FT_EPOCHS" python3 scripts/v19_qat_input_qact_finetune.py --quant-alpha 1

log "=== BIT_EXACT=1 convert + csim pipeline ==="
BIT_EXACT=1 SKIP_FINETUNE=1 bash scripts/run_v19_qat_resume.sh

log "=== DONE — check results/v19_route1_gates.json ==="
