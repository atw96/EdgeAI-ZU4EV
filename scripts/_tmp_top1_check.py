#!/usr/bin/env python3
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'scripts'))
import os
os.environ.setdefault('DENSE_NPZ', str(REPO / 'deploy' / 'dense_head.npz'))
from dma_infer_common import apply_ps_dense

d = json.loads((REPO / 'results/gap_csim_keras_align.json').read_text())
data = np.load(REPO / 'deploy/cifar10_bench.npz', allow_pickle=True)
labels = data['labels'][:100]
samples = d['samples'][:100]

k_ok = c_ok = 0
for i, s in enumerate(samples):
    lab = int(labels[i])
    kg = s['keras_gap'][:24]
    cs = s['csim_gap'][:24]
    if int(np.argmax(apply_ps_dense(kg))) == lab:
        k_ok += 1
    if int(np.argmax(apply_ps_dense(cs))) == lab:
        c_ok += 1

print('keras_gap+ps top1', k_ok, '%')
print('csim_gap+ps top1', c_ok, '%')
print('summary mae', d['summary'])
