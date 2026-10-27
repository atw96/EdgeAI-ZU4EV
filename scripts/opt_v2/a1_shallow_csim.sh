#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
# After P5 releases Vivado, csim the shallow-FIFO A1' on 1000 images.
# Target host: wsl-local.
set -euo pipefail
H=${EDGEAI_ROOT}
cd "$H"
echo "[$(date '+%F %T')] waiting for P5"
while [[ ! -f "$H/results/opt_v2/p5_indexloop.json" ]]; do
  sleep 30
done
while pgrep -f 'vivado_hls|p5_indexloop.sh' >/dev/null; do
  sleep 15
done
LOG="$H/results/opt_v2/logs/a1_shallow_csim.log"
exec > >(tee -a "$LOG") 2>&1
echo "[$(date '+%F %T')] shallow A1' csim N=1000"
source ${HOME}/miniconda3/etc/profile.d/conda.sh
conda activate edgeai_39
export PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python
export SKIP_BOARD=1 OPT_V2_KEEP_RF=1
export N_GAP_COMPARE=1000
export CSIM_NPZ="$H/deploy/cifar10_bench_1k.npz"
bash scripts/run_gap_axi_csim.sh
cp -f notebooks/hls4ml_prj/tb_data/csim_results.log "$H/results/opt_v2/a1_shallow_csim.log"
export P1_GATE_JSON="$H/results/opt_v2/a1_shallow_csim_gate.json"
rm -f "$P1_GATE_JSON"
python3 -u scripts/opt_v2/p1_numeric.py \
  "$H/results/opt_v2/p1_narrow_a1_csim.log" \
  "$H/results/opt_v2/a1_shallow_csim.log"
echo "[$(date '+%F %T')] shallow csim done"
