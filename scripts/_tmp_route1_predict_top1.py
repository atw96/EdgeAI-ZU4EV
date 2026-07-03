#!/usr/bin/env python3
import json
import sys
from pathlib import Path
import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'scripts'))
from dma_infer_common import apply_ps_dense
from v19_hls_config_common import load_gap_model, build_hls_config, configure_rounding_saturation

import hls4ml

gap = load_gap_model()
configure_rounding_saturation(gap)
cfg = build_hls_config(gap, bit_exact=True)
hm = hls4ml.converters.convert_from_keras_model(
    gap, hls_config=cfg, output_dir=str(REPO / 'notebooks' / 'hls4ml_prj_v19_bitexact_tmp'),
    backend='Vivado', io_type='io_stream', part='xczu4ev-sfvc784-1-i', clock_period=5,
    bit_exact=True,
)
hm.compile()

data = np.load(REPO / 'deploy' / 'cifar10_bench.npz', allow_pickle=True)
labels = data['labels'][:100]
correct = 0
maes = []
gap_k = load_gap_model()
for i in range(100):
    raw = bytes(data['payloads'][i])
    x = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 1024.0
    x = x.reshape(1, 32, 32, 3)
    kg = np.ravel(gap_k.predict(x, verbose=0))[:24]
    hp = np.ravel(hm.predict(np.ascontiguousarray(x)))[:24]
    maes.append(float(np.mean(np.abs(kg - hp))))
    if int(np.argmax(apply_ps_dense(hp))) == int(labels[i]):
        correct += 1
print(json.dumps({'top1': correct, 'mae': float(np.mean(maes))}, indent=2))
