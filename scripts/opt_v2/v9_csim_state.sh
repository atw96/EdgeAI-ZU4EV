#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
H=${EDGEAI_ROOT}
ls -l --time-style=full-iso "$H/results/opt_v2/logs/v9_csim_synth.log" "$H/results/opt_v2/v5_synth/csim_results.log" "$H/results/opt_v2/v5_synth/csim_gap.npy" 2>&1 | head
echo "--- v5 lines ---"
wc -l "$H/results/opt_v2/v5_synth/csim_results.log" 2>/dev/null || true
echo "--- a2l log lines ---"
wc -l "$H/results/opt_v2/logs/v9_csim_synth.log"
echo "--- npz keys ---"
source ${HOME}/miniconda3/etc/profile.d/conda.sh
conda activate edgeai_39
python3 - << 'PY'
import numpy as np
p=np.load(__import__("os").environ["EDGEAI_ROOT"] + '/results/opt_v2/v5_synth/synth_packed.npz')
print(p.files, {k: getattr(p[k], "shape", None) for k in p.files})
PY
