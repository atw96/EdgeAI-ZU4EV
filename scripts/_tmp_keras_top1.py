#!/usr/bin/env python3
import sys
from pathlib import Path
import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'scripts'))
from dma_infer_common import apply_ps_dense
from v19_hls_config_common import load_gap_model

data = np.load(REPO / 'deploy' / 'cifar10_bench.npz', allow_pickle=True)
gap = load_gap_model()
labels = data['labels'][:100]
correct = 0
for i in range(100):
    raw = bytes(data['payloads'][i])
    x = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 1024.0
    x = x.reshape(1, 32, 32, 3)
    g = np.ravel(gap.predict(x, verbose=0))[:24]
    pred = int(np.argmax(apply_ps_dense(g)))
    if pred == labels[i]:
        correct += 1
print('keras_gap_ps_top1_pct', correct)
