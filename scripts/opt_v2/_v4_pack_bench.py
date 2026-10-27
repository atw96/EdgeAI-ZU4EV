#!/usr/bin/env python3
"""Pack the object-array bench npz into a contiguous uint8 matrix.

Indexing the object array costs ~100 ms per image. The board run was
spending essentially all of its time there.
"""
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
src = REPO / 'deploy' / 'cifar10_bench_10k.npz'
dst = REPO / 'results' / 'opt_v2' / 'bench10k_packed.npz'
t0 = time.perf_counter()
data = np.load(src, allow_pickle=True)
payloads = data['payloads']
labels = np.asarray(data['labels'], dtype=np.int32)
t1 = time.perf_counter()
rows = payloads.tolist()
t2 = time.perf_counter()
mat = np.empty((len(rows), 6144), dtype=np.uint8)
for i, row in enumerate(rows):
    mat[i] = np.frombuffer(row, dtype=np.uint8)
t3 = time.perf_counter()
np.savez(dst, payloads=mat, labels=labels)
print('load %.2fs tolist %.2fs pack %.2fs n %d bytes %d' % (
    t1 - t0, t2 - t1, t3 - t2, len(rows), len(rows[0])))
print(dst)
