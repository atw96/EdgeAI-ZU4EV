#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
# P1 controlled convert. Target host: wsl-local, user atw.
# Prediction is results/opt_v2/p1_prediction.json. Weight drift stops the script
# before csim and before any later synthesis.
set -euo pipefail
REPO=${EDGEAI_ROOT}
cd "$REPO"
LOG="$REPO/results/opt_v2/logs/p1_controlled.log"
exec > >(tee -a "$LOG") 2>&1
echo "[$(date '+%F %T')] P1 start"
source ${HOME}/miniconda3/etc/profile.d/conda.sh
conda activate edgeai_hls4ml13
export PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python
export BIT_EXACT=1
export GAP_ONLY=1
test -f deploy/cifar10_bench_1k.npz

python3 scripts/opt_v2/set_rf.py --variant P4
export BAK_TAG=p1_old_a1csynth
python3 -u scripts/v19_bitexact_convert.py
rm -rf "$REPO/results/opt_v2/p1_p4_firmware"
mkdir -p "$REPO/results/opt_v2/p1_p4_firmware"
cp -a notebooks/hls4ml_prj/firmware/weights "$REPO/results/opt_v2/p1_p4_firmware/weights"
cp -a notebooks/hls4ml_prj/firmware/defines.h notebooks/hls4ml_prj/firmware/parameters.h \
  "$REPO/results/opt_v2/p1_p4_firmware/"

python3 scripts/opt_v2/set_rf.py --variant A1prime
export BAK_TAG=p1_p4
python3 -u scripts/v19_bitexact_convert.py
rm -rf "$REPO/results/opt_v2/p1_a1_firmware"
mkdir -p "$REPO/results/opt_v2/p1_a1_firmware"
cp -a notebooks/hls4ml_prj/firmware/weights "$REPO/results/opt_v2/p1_a1_firmware/weights"
cp -a notebooks/hls4ml_prj/firmware/defines.h notebooks/hls4ml_prj/firmware/parameters.h \
  "$REPO/results/opt_v2/p1_a1_firmware/"

if ! python3 scripts/opt_v2/p1_static_diff.py \
  "$REPO/results/opt_v2/p1_p4_firmware" \
  "$REPO/results/opt_v2/p1_a1_firmware" \
  "$REPO/results/opt_v2/p1_static_diff.json"
then
  echo "P1 STOP: weight or defines drift. No csim, no further synthesis."
  exit 2
fi
echo "[$(date '+%F %T')] static diff passed; csim both projects on 1000 test images"

export SKIP_BOARD=1
export N_GAP_COMPARE=1000
export CSIM_NPZ="$REPO/deploy/cifar10_bench_1k.npz"
export OPT_V2_KEEP_RF=1

# P4 project is the backup. Park the live A1' tree, csim, then put A1' back.
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

conda activate edgeai_39
export CSIM_NPZ="$REPO/deploy/cifar10_bench_1k.npz"
export N_GAP_COMPARE=1000
export P1_GATE_JSON="$REPO/results/opt_v2/p1_gate.json"
if ! python3 -u scripts/opt_v2/p1_numeric.py \
  "$REPO/results/opt_v2/p1_p4_csim.log" \
  "$REPO/results/opt_v2/p1_a1_csim.log"
then
  echo "P1 STOP: numeric gate failed. No P2b/P3/P4/P5 synthesis."
  exit 3
fi
echo "[$(date '+%F %T')] P1 gate passed"
