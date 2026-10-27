#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
# Continue P1 after the static classifier fix. Does not reconvert.
# Target host: wsl-local.
set -euo pipefail
REPO=${EDGEAI_ROOT}
cd "$REPO"
LOG="$REPO/results/opt_v2/logs/p1_csim.log"
exec > >(tee -a "$LOG") 2>&1
echo "[$(date '+%F %T')] P1 csim continuation"
rm -f "$REPO/results/opt_v2/p1_static_diff.json"
python3 scripts/opt_v2/p1_static_diff.py \
  "$REPO/results/opt_v2/p1_p4_firmware" \
  "$REPO/results/opt_v2/p1_a1_firmware" \
  "$REPO/results/opt_v2/p1_static_diff.json"
echo "[$(date '+%F %T')] static diff passed"

export SKIP_BOARD=1
export N_GAP_COMPARE=1000
export CSIM_NPZ="$REPO/deploy/cifar10_bench_1k.npz"
export OPT_V2_KEEP_RF=1
test -d "$REPO/notebooks/hls4ml_prj.bak_bitexact_p1_p4"
test -d "$REPO/notebooks/hls4ml_prj"

hold="$REPO/notebooks/hls4ml_prj.p1_hold"
rm -rf "$hold"
mv "$REPO/notebooks/hls4ml_prj" "$hold"
mv "$REPO/notebooks/hls4ml_prj.bak_bitexact_p1_p4" "$REPO/notebooks/hls4ml_prj"
bash scripts/run_gap_axi_csim.sh
cp -f notebooks/hls4ml_prj/tb_data/csim_results.log "$REPO/results/opt_v2/p1_p4_csim.log"
wc -l "$REPO/results/opt_v2/p1_p4_csim.log"
mv "$REPO/notebooks/hls4ml_prj" "$REPO/notebooks/hls4ml_prj.bak_bitexact_p1_p4"
mv "$hold" "$REPO/notebooks/hls4ml_prj"

bash scripts/run_gap_axi_csim.sh
cp -f notebooks/hls4ml_prj/tb_data/csim_results.log "$REPO/results/opt_v2/p1_a1_csim.log"
wc -l "$REPO/results/opt_v2/p1_a1_csim.log"

source ${HOME}/miniconda3/etc/profile.d/conda.sh
conda activate edgeai_39
export PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python
export P1_GATE_JSON="$REPO/results/opt_v2/p1_gate.json"
rm -f "$P1_GATE_JSON"
python3 -u scripts/opt_v2/p1_numeric.py \
  "$REPO/results/opt_v2/p1_p4_csim.log" \
  "$REPO/results/opt_v2/p1_a1_csim.log"
echo "[$(date '+%F %T')] P1 numeric done"
