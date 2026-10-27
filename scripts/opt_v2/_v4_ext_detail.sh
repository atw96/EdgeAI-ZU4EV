#!/bin/bash
source ${HOME}/miniconda3/etc/profile.d/conda.sh
conda activate edgeai_39
python3 - <<'PY'
import numpy as np
from pathlib import Path
out = (Path(__import__("os").environ["EDGEAI_ROOT"]) / 'results/opt_v2')
lines = (out/'v4_csim_extreme.log').read_text().splitlines()
print('extreme log lines', len(lines), 'widths', [len(l.split()) for l in lines])
csim = np.array([[float(x) for x in line.split()] for line in lines[:4]])
board = np.load(out/'board_gap_extreme.npy').astype(np.float64)/1024.0
ker = np.load(out/'v4_keras_gap_extreme.npy').astype(np.float64).reshape(4,-1)[:,:24]
z = np.load(out/'bench_extreme.npz')
raw = np.frombuffer(z['payloads'][0].tobytes(), dtype=np.int16)
print('black payload min/max', int(raw.min()), int(raw.max()))
names=['black','white','checker','sat']
for i,name in enumerate(names):
    db = np.abs(np.rint(csim[i]*1024)-np.rint(board[i]*1024))
    dk = np.abs(np.rint(csim[i]*1024)-np.rint(ker[i]*1024))
    j = int(np.argmax(db))
    k = int(np.argmax(dk))
    print(name, 'worst_board_ch', j, 'csim', round(float(csim[i,j]),4), 'board', round(float(board[i,j]),4),
          'worst_keras_ch', k, 'keras', round(float(ker[i,k]),4), 'csim_k', round(float(csim[i,k]),4))
print('black csim', np.round(csim[0],3).tolist())
print('black board', np.round(board[0],3).tolist())
print('black keras', np.round(ker[0],3).tolist())
PY
