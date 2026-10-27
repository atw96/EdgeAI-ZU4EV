#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
# Private tb_data inside the csim build directory. The shipped tb_data is a
# symlink into the RC1 tree; this script removes only that symlink and puts
# it back. It never writes through the link.
set -uo pipefail
H=${EDGEAI_ROOT}
BUILD=$H/notebooks/hls4ml_prj_a2l/myproject_prj/solution1/csim/build
LINK=$BUILD/tb_data
SYN=$H/results/opt_v2/v5_synth
OUT=$H/results/opt_v2/a2l
LOG=$H/results/opt_v2/logs/v9_csim729b.log
mkdir -p "$OUT" "$H/results/opt_v2/logs"
if [ ! -L "$LINK" ]; then
  echo "refusing: $LINK is not a symlink" | tee "$LOG"
  exit 1
fi
TARGET=$(readlink "$LINK")
restore_link() {
  if [ -L "$LINK" ]; then
    return 0
  fi
  rm -rf "$LINK"
  ln -s "$TARGET" "$LINK"
}
trap restore_link EXIT
rm "$LINK"
mkdir "$LINK"
cp -f "$SYN/tb_input_features.dat" "$LINK/tb_input_features.dat"
cp -f "$SYN/tb_output_predictions.dat" "$LINK/tb_output_predictions.dat"
echo "[$(date '+%F %T')] csim729b start target $TARGET" | tee "$LOG"
cd "$BUILD"
./csim.exe > "$LOG.stdout" 2>&1
rc=$?
echo "[$(date '+%F %T')] csim exe rc $rc" | tee -a "$LOG"
cp -f "$LINK/csim_results.log" "$OUT/synth729_csim.log"
wc -l "$OUT/synth729_csim.log" | tee -a "$LOG"
source ${HOME}/miniconda3/etc/profile.d/conda.sh
conda activate edgeai_39
python3 - << 'PY'
import numpy as np
from pathlib import Path
H = Path(__import__("os").environ["EDGEAI_ROOT"])
out = H / "results/opt_v2/a2l"
lines = [ln for ln in (out / "synth729_csim.log").read_text().splitlines() if ln.strip()]
ref_lines = [ln for ln in (H / "results/opt_v2/v5_synth/csim_results.log").read_text().splitlines() if ln.strip()]
gap = np.array([[float(x) for x in line.split()] for line in lines], dtype=np.float64)
ref = np.array([[float(x) for x in line.split()] for line in ref_lines], dtype=np.float64)
lsb = np.rint(gap * 1024.0).astype(np.int32)
ref_lsb = np.rint(ref * 1024.0).astype(np.int32)
np.save(out / "synth729_csim_gap.npy", gap.astype(np.float32))
lsb.tofile(out / "synth729_golden.bin")
same = gap.shape == ref.shape and int(np.max(np.abs(lsb - ref_lsb))) == 0
print("a2l", gap.shape, "rc1", ref.shape, "max_abs_lsb", int(np.max(np.abs(lsb - ref_lsb))) if gap.shape == ref.shape else "shape")
print("bit_exact", same)
PY
echo "[$(date '+%F %T')] csim729b done" | tee -a "$LOG"
