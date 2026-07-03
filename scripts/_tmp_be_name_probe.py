#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'scripts'))
from v19_hls_config_common import load_gap_model, build_hls_config, configure_rounding_saturation
from v19_bitexact_probe import _firmware_layer_ops, _walk_graph
from dma_infer_common import apply_ps_dense

import hls4ml
import numpy as np

os.environ['BIT_EXACT'] = '1'
gap = load_gap_model()
configure_rounding_saturation(gap)
cfg = build_hls_config(gap, bit_exact=True)
out = REPO / 'notebooks' / 'hls4ml_prj_v19_be_name_tmp'
hm = hls4ml.converters.convert_from_keras_model(
    gap, hls_config=cfg, output_dir=str(out),
    backend='Vivado', io_type='io_stream', part='xczu4ev-sfvc784-1-i', clock_period=5,
    bit_exact=True,
)
hm.compile()
_, fpq = _walk_graph(hm)
ops = _firmware_layer_ops(out)
defines = (out / 'firmware' / 'defines.h').read_text()
result_line = [l.strip() for l in defines.splitlines() if ' result_t;' in l][-1]
# table sizes
params = (out / 'firmware' / 'parameters.h').read_text()
sizes = [l.strip() for l in params.splitlines() if 'table_size' in l][:8]

data = np.load(REPO / 'deploy' / 'cifar10_bench.npz', allow_pickle=True)
os.environ['DENSE_NPZ'] = str(REPO / 'deploy' / 'dense_head.npz')
correct = 0
for i in range(100):
    raw = bytes(data['payloads'][i])
    x = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 1024.0
    x = x.reshape(1, 32, 32, 3)
    hp = np.ravel(hm.predict(np.ascontiguousarray(x)))[:24]
    if int(np.argmax(apply_ps_dense(hp))) == int(data['labels'][i]):
        correct += 1
print(json.dumps({
    'fpq_count': fpq,
    'relu_ops': ops,
    'result_t': result_line,
    'table_sizes': sizes,
    'top1': correct,
}, indent=2))
