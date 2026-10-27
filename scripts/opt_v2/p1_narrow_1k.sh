#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
# MAE is back to 0.026. Finish the P4/A1' pair at N=1000.
# Target host: wsl-local.
set -euo pipefail
REPO=${EDGEAI_ROOT}
cd "$REPO"
LOG="$REPO/results/opt_v2/logs/p1_narrow_1k.log"
exec > >(tee -a "$LOG") 2>&1
echo "[$(date '+%F %T')] convert A1prime with narrow precision"
source ${HOME}/miniconda3/etc/profile.d/conda.sh
conda activate edgeai_hls4ml13
export PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python
export BIT_EXACT=0
export GAP_ONLY=1
test -d "$REPO/results/opt_v2/p1_narrow_p4_firmware/weights"
python3 scripts/opt_v2/set_rf.py --variant A1prime
export BAK_TAG=p1_narrow_p4
python3 -u scripts/v19_bitexact_convert.py
rm -rf "$REPO/results/opt_v2/p1_narrow_a1_firmware"
mkdir -p "$REPO/results/opt_v2/p1_narrow_a1_firmware"
cp -a notebooks/hls4ml_prj/firmware/weights "$REPO/results/opt_v2/p1_narrow_a1_firmware/weights"
cp -a notebooks/hls4ml_prj/firmware/defines.h notebooks/hls4ml_prj/firmware/parameters.h \
  "$REPO/results/opt_v2/p1_narrow_a1_firmware/"
rm -f "$REPO/results/opt_v2/p1_narrow_static_diff.json"
python3 scripts/opt_v2/p1_static_diff.py \
  "$REPO/results/opt_v2/p1_narrow_p4_firmware" \
  "$REPO/results/opt_v2/p1_narrow_a1_firmware" \
  "$REPO/results/opt_v2/p1_narrow_static_diff.json"

export SKIP_BOARD=1 OPT_V2_KEEP_RF=1
export N_GAP_COMPARE=1000
export CSIM_NPZ="$REPO/deploy/cifar10_bench_1k.npz"
hold="$REPO/notebooks/hls4ml_prj.p1_hold"
rm -rf "$hold"
mv "$REPO/notebooks/hls4ml_prj" "$hold"
mv "$REPO/notebooks/hls4ml_prj.bak_bitexact_p1_narrow_p4" "$REPO/notebooks/hls4ml_prj"
bash scripts/run_gap_axi_csim.sh
cp -f notebooks/hls4ml_prj/tb_data/csim_results.log "$REPO/results/opt_v2/p1_narrow_p4_csim.log"
wc -l "$REPO/results/opt_v2/p1_narrow_p4_csim.log"
mv "$REPO/notebooks/hls4ml_prj" "$REPO/notebooks/hls4ml_prj.bak_bitexact_p1_narrow_p4"
mv "$hold" "$REPO/notebooks/hls4ml_prj"
bash scripts/run_gap_axi_csim.sh
cp -f notebooks/hls4ml_prj/tb_data/csim_results.log "$REPO/results/opt_v2/p1_narrow_a1_csim.log"
wc -l "$REPO/results/opt_v2/p1_narrow_a1_csim.log"

conda activate edgeai_39
export P1_GATE_JSON="$REPO/results/opt_v2/p1_narrow_gate.json"
rm -f "$P1_GATE_JSON"
set +e
python3 -u scripts/opt_v2/p1_numeric.py \
  "$REPO/results/opt_v2/p1_narrow_p4_csim.log" \
  "$REPO/results/opt_v2/p1_narrow_a1_csim.log"
rc=$?
set -e
echo "numeric rc=$rc"
echo "[$(date '+%F %T')] narrow 1k done"
exit "$rc"
