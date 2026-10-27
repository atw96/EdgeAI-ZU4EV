#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
# csim the 729 synthetic frames with the existing RC1 csim.exe.
# Target host: wsl-local. Restores the 10k testbench files afterwards.
set -euo pipefail
REPO=${EDGEAI_ROOT}
HLS=$REPO/notebooks/hls4ml_prj
TB=$HLS/tb_data
BUILD=$HLS/myproject_prj/solution1/csim/build
SYN=$REPO/results/opt_v2/v5_synth
LOG=$REPO/results/opt_v2/logs/v5_csim_synth.log
mkdir -p "$REPO/results/opt_v2/logs"
exec > >(tee -a "$LOG") 2>&1
echo "[$(date '+%F %T')] synth csim"
test -f "$SYN/tb_input_features.dat"
if [ ! -f "$TB/tb_input_features.dat.full10k" ]; then
  cp -f "$TB/tb_input_features.dat" "$TB/tb_input_features.dat.full10k"
  cp -f "$TB/tb_output_predictions.dat" "$TB/tb_output_predictions.dat.full10k"
fi
cp -f "$SYN/tb_input_features.dat" "$TB/tb_input_features.dat"
cp -f "$SYN/tb_output_predictions.dat" "$TB/tb_output_predictions.dat"
source /tools/Xilinx/Vivado/2020.1/settings64.sh
cd "$BUILD"
./csim.exe
cp -f "$TB/csim_results.log" "$SYN/csim_results.log"
cp -f "$TB/tb_input_features.dat.full10k" "$TB/tb_input_features.dat"
cp -f "$TB/tb_output_predictions.dat.full10k" "$TB/tb_output_predictions.dat"
source ${HOME}/miniconda3/etc/profile.d/conda.sh
conda activate edgeai_39
python3 - <<'PY'
import numpy as np
from pathlib import Path
syn = (Path(__import__("os").environ["EDGEAI_ROOT"]) / 'results/opt_v2/v5_synth')
lines = (syn / "csim_results.log").read_text().splitlines()
gap = np.array([[float(x) for x in line.split()] for line in lines], dtype=np.float32)
np.save(syn / "csim_gap.npy", gap)
print("csim", gap.shape)
PY
echo "[$(date '+%F %T')] synth csim done"
