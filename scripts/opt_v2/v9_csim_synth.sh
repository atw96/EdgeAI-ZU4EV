#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
# A2-L csim of the 729 synthetic frames. Does not touch the RC1 HLS tree.
set -euo pipefail
H=${EDGEAI_ROOT}
HLS=$H/notebooks/hls4ml_prj_a2l
TB=$HLS/tb_data
BUILD=$HLS/myproject_prj/solution1/csim/build
SYN=$H/results/opt_v2/v5_synth
OUT=$H/results/opt_v2/a2l
LOG=$H/results/opt_v2/logs/v9_csim_synth.log
mkdir -p "$H/results/opt_v2/logs" "$OUT" "$TB"
exec > >(tee -a "$LOG") 2>&1
echo "[$(date '+%F %T')] a2l synth csim"
test -x "$BUILD/csim.exe"
test -f "$SYN/tb_input_features.dat"
restore() {
  if [ -f "$TB/tb_input_features.dat.v9bak" ]; then
    mv -f "$TB/tb_input_features.dat.v9bak" "$TB/tb_input_features.dat"
  fi
  if [ -f "$TB/tb_output_predictions.dat.v9bak" ]; then
    mv -f "$TB/tb_output_predictions.dat.v9bak" "$TB/tb_output_predictions.dat"
  fi
}
trap restore EXIT
if [ -f "$TB/tb_input_features.dat" ]; then
  cp -a "$TB/tb_input_features.dat" "$TB/tb_input_features.dat.v9bak"
fi
if [ -f "$TB/tb_output_predictions.dat" ]; then
  cp -a "$TB/tb_output_predictions.dat" "$TB/tb_output_predictions.dat.v9bak"
fi
cp -f "$SYN/tb_input_features.dat" "$TB/tb_input_features.dat"
cp -f "$SYN/tb_output_predictions.dat" "$TB/tb_output_predictions.dat"
source /tools/Xilinx/Vivado/2020.1/settings64.sh
cd "$BUILD"
./csim.exe
cp -f "$TB/csim_results.log" "$OUT/synth729_csim.log"
source ${HOME}/miniconda3/etc/profile.d/conda.sh
conda activate edgeai_39
python3 - << 'PY'
import numpy as np
from pathlib import Path
out = (Path(__import__("os").environ["EDGEAI_ROOT"]) / 'results/opt_v2/a2l')
lines = (out / "synth729_csim.log").read_text().splitlines()
gap = np.array([[float(x) for x in line.split()] for line in lines if line.strip()], dtype=np.float64)
lsb = np.rint(gap * 1024.0).astype(np.int32)
np.save(out / "synth729_csim_gap.npy", gap.astype(np.float32))
lsb.tofile(out / "synth729_golden.bin")
print("csim", gap.shape, "max_abs_lsb_roundtrip", int(np.max(np.abs(lsb))))
PY
echo "[$(date '+%F %T')] a2l synth csim done"
