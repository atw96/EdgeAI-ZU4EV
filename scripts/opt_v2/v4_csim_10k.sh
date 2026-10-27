#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
# 10000-image csim of the shallow narrow A1' project. No board.
# Target host: wsl-local.
set -euo pipefail
REPO=${EDGEAI_ROOT}
cd "$REPO"
LOG=$REPO/results/opt_v2/logs/v4_csim_10k.log
mkdir -p "$REPO/results/opt_v2/logs"
exec > >(tee -a "$LOG") 2>&1
echo "[$(date '+%F %T')] csim 10k"
source ${HOME}/miniconda3/etc/profile.d/conda.sh
conda activate edgeai_39
export PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python
export SKIP_BOARD=1 OPT_V2_KEEP_RF=1
export N_GAP_COMPARE=10000
export CSIM_NPZ=$REPO/deploy/cifar10_bench_10k.npz
bash scripts/run_gap_axi_csim.sh
cp -f notebooks/hls4ml_prj/tb_data/csim_results.log "$REPO/results/opt_v2/v4_csim_10k.log"
wc -l "$REPO/results/opt_v2/v4_csim_10k.log"
export P1_GATE_JSON=$REPO/results/opt_v2/v4_d3_csim10k.json
rm -f "$P1_GATE_JSON"
python3 -u scripts/opt_v2/p1_numeric.py \
  "$REPO/results/opt_v2/v4_csim_10k.log" \
  "$REPO/results/opt_v2/v4_csim_10k.log"
echo "[$(date '+%F %T')] 10k gate done"
