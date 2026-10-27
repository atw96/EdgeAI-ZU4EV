#!/bin/bash
source ${HOME}/miniconda3/etc/profile.d/conda.sh
conda activate edgeai_39
python3 - <<'PY'
import numpy as np
from pathlib import Path
out = (Path(__import__("os").environ["EDGEAI_ROOT"]) / 'results/opt_v2')
a = np.load(out/'board_gap_extreme.npy')
b = np.load(out/'board_gap_extreme2.npy')
c = np.load(out/'board_gap_extreme3.npy')
print('e2 vs e3', int(np.max(np.abs(b.astype(np.int32)-c.astype(np.int32)))))
print('e1 vs e2', int(np.max(np.abs(a.astype(np.int32)-b.astype(np.int32)))))
print('shapes', a.shape, b.shape, c.shape)
PY
