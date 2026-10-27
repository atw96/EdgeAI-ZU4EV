#!/bin/bash
set -euo pipefail
source ${HOME}/miniconda3/etc/profile.d/conda.sh
conda activate edgeai_39
python3 - <<'PY'
import numpy as np
from pathlib import Path
repo = Path(__import__("os").environ["EDGEAI_ROOT"])
board = np.load(repo / "results/opt_v2/smoke_gap.npy")
lines = (repo / "results/opt_v2/a1_shallow_csim.log").read_text().splitlines()
csim = np.array([[float(x) for x in lines[i].split()] for i in range(len(board))])
d = np.abs(board.astype(np.float64) - csim)
lsb = np.abs(np.rint(board * 1024.0) - np.rint(csim * 1024.0))
lat = np.load(repo / "results/opt_v2/smoke_lat_ms.npy")
print("shape", board.shape, csim.shape)
print("max_abs", float(d.max()), "max_lsb", float(lsb.max()))
print("median_ms", float(np.median(lat)), "min", float(lat.min()), "max", float(lat.max()))
print("lat", [round(float(x), 4) for x in lat])
print("n_mismatch", int(np.sum(lsb != 0)))
PY
