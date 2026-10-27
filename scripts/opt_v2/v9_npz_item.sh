#!/bin/bash
source ${HOME}/miniconda3/etc/profile.d/conda.sh
conda activate edgeai_39
python3 - << 'PY'
import numpy as np
p=np.load(__import__("os").environ["EDGEAI_ROOT"] + '/deploy/cifar10_bench_10k.npz', allow_pickle=True)
print("keys", p.files)
for k in p.files:
    a=p[k]
    print(k, type(a), getattr(a, "shape", None), getattr(a, "dtype", None))
x=p["payloads"]
item=x[0]
print("item0", type(item), getattr(item, "shape", None), getattr(item, "dtype", None), len(item) if hasattr(item, "__len__") else None)
lab=p["labels"]
print("label0", lab[0] if getattr(lab, "shape", None) else lab)
PY
