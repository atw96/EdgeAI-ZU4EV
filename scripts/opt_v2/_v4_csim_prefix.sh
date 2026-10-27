#!/bin/bash
source ${HOME}/miniconda3/etc/profile.d/conda.sh
conda activate edgeai_39
python3 - <<'PY'
from pathlib import Path
import numpy as np
repo = Path(__import__("os").environ["EDGEAI_ROOT"])
new = (repo/'notebooks/hls4ml_prj/tb_data/csim_results.log').read_text().splitlines()
old = (repo/'results/opt_v2/a1_shallow_csim.log').read_text().splitlines()
n = min(len(new), len(old), 200)
a = np.array([[float(x) for x in new[i].split()] for i in range(n)])
b = np.array([[float(x) for x in old[i].split()] for i in range(n)])
lsb = np.max(np.abs(np.rint(a*1024)-np.rint(b*1024)))
print('compared', n, 'of new', len(new), 'max_lsb', float(lsb), 'max_abs', float(np.max(np.abs(a-b))))
PY
