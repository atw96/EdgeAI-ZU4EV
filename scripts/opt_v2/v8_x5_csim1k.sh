#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
set -euo pipefail
H=${EDGEAI_ROOT}
cd "$H"
LOG=$H/results/opt_v2/logs/v8_x5_csim1k.log
exec > >(tee -a "$LOG") 2>&1
echo "[$(date '+%F %T')] csim 1000 on parked A2-L tree"
mv notebooks/hls4ml_prj notebooks/hls4ml_prj_rc1_hold
mv notebooks/hls4ml_prj_a2l notebooks/hls4ml_prj
set +e
SKIP_BOARD=1 N_GAP_COMPARE=1000 CSIM_NPZ="$H/deploy/cifar10_bench_1k.npz" bash scripts/run_gap_axi_csim.sh
RC=$?
set -e
cp -f notebooks/hls4ml_prj/tb_data/csim_results.log results/opt_v2/a2l/csim_results_1k.log || true
mv notebooks/hls4ml_prj notebooks/hls4ml_prj_a2l
mv notebooks/hls4ml_prj_rc1_hold notebooks/hls4ml_prj
echo "CSIM_RC $RC"
python3 scripts/opt_v2/bitexact_gap_compare.py \
  results/opt_v2/a1_shallow_csim.log \
  results/opt_v2/a2l/csim_results_1k.log --n 1000
echo "COMPARE_DONE"
