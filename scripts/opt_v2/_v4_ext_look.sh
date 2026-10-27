#!/bin/bash
source ${HOME}/miniconda3/etc/profile.d/conda.sh
conda activate edgeai_39
python3 - <<'PY'
import numpy as np
from pathlib import Path
out = (Path(__import__("os").environ["EDGEAI_ROOT"]) / 'results/opt_v2')
ext = np.load(out/'board_gap_extreme.npy')
ker = np.load(out/'v4_keras_gap_extreme.npy')
print('shapes', ext.shape, ker.shape, ext.dtype, ker.dtype)
names = ['black','white','checker','sat']
k = ker.reshape(ker.shape[0], -1)
e = ext.astype(np.float64)/1024.0
for i, name in enumerate(names):
    d = np.abs(e[i] - k[i, :e.shape[1]])
    print(name, 'max_abs', float(d.max()), 'board', np.round(e[i,:6], 4), 'keras', np.round(k[i,:6], 4))
PY
