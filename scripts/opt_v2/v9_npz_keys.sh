#!/bin/bash
source ${HOME}/miniconda3/etc/profile.d/conda.sh
conda activate edgeai_39
python3 - << 'PY'
import numpy as np
p=np.load(__import__("os").environ["EDGEAI_ROOT"] + '/deploy/cifar10_bench_10k.npz')
print(p.files)
for k in p.files:
    a=p[k]
    print(k, getattr(a,"shape",None), getattr(a,"dtype",None))
PY
