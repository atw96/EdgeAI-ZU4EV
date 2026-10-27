#!/bin/bash
source ${HOME}/miniconda3/etc/profile.d/conda.sh
conda activate edgeai_39
python3 - <<'PY'
import numpy as np, time
p=__import__("os").environ["EDGEAI_ROOT"] + '/deploy/cifar10_bench_10k.npz'
t0=time.perf_counter()
d=np.load(p, allow_pickle=True)
print('load', round(time.perf_counter()-t0, 3), 'n', len(d['payloads']))
x=d['payloads'][0]
print(type(x), getattr(x,'shape',None), len(bytes(x)) if not isinstance(x, (bytes, bytearray)) else len(x))
t1=time.perf_counter()
for i in range(100):
    bytes(d['payloads'][i])
print('100 bytes()', round(time.perf_counter()-t1, 3))
PY
