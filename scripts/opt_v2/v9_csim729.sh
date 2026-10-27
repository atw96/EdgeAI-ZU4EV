#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
# A2-L csim of the 729 synthetic frames.
# The build directory's tb_data is a symlink into the RC1 tree. This run
# uses a private working directory and does not follow that symlink.
set -uo pipefail
H=${EDGEAI_ROOT}
BUILD=$H/notebooks/hls4ml_prj_a2l/myproject_prj/solution1/csim/build
SYN=$H/results/opt_v2/v5_synth
OUT=$H/results/opt_v2/a2l
WORK=/tmp/v9_csim729
LOG=$H/results/opt_v2/logs/v9_csim729.log
mkdir -p "$OUT" "$H/results/opt_v2/logs"
rm -rf "$WORK"
mkdir -p "$WORK/tb_data"
cp -f "$SYN/tb_input_features.dat" "$WORK/tb_data/tb_input_features.dat"
cp -f "$SYN/tb_output_predictions.dat" "$WORK/tb_data/tb_output_predictions.dat"
echo "[$(date '+%F %T')] csim729 start" | tee "$LOG"
cd "$WORK"
"$BUILD/csim.exe" > "$LOG.stdout" 2>&1
rc=$?
echo "[$(date '+%F %T')] csim exe rc $rc" | tee -a "$LOG"
cp -f "$WORK/tb_data/csim_results.log" "$OUT/synth729_csim.log"
wc -l "$OUT/synth729_csim.log" | tee -a "$LOG"
source ${HOME}/miniconda3/etc/profile.d/conda.sh
conda activate edgeai_39
python3 - << 'PY'
import numpy as np
from pathlib import Path
H = Path(__import__("os").environ["EDGEAI_ROOT"])
out = H / "results/opt_v2/a2l"
lines = (out / "synth729_csim.log").read_text().splitlines()
gap = np.array([[float(x) for x in line.split()] for line in lines if line.strip()], dtype=np.float64)
ref_lines = (H / "results/opt_v2/v5_synth/csim_results.log").read_text().splitlines()
ref = np.array([[float(x) for x in line.split()] for line in ref_lines if line.strip()], dtype=np.float64)
lsb = np.rint(gap * 1024.0).astype(np.int32)
ref_lsb = np.rint(ref * 1024.0).astype(np.int32)
np.save(out / "synth729_csim_gap.npy", gap.astype(np.float32))
lsb.tofile(out / "synth729_golden.bin")
print("a2l", gap.shape, "rc1", ref.shape)
print("max_abs_lsb", int(np.max(np.abs(lsb - ref_lsb))))
print("text_equal", lines == ref_lines)
PY
echo "[$(date '+%F %T')] csim729 done" | tee -a "$LOG"
