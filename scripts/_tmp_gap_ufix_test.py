#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path
import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'scripts'))
from v19_hls_config_common import load_gap_model, build_hls_config, configure_rounding_saturation
from dma_infer_common import apply_ps_dense
import hls4ml

gap = load_gap_model()
configure_rounding_saturation(gap)
cfg = build_hls_config(gap, bit_exact=False)
cfg['LayerName']['gap']['Precision'] = {
    'result': 'ap_ufixed<12,2,RND_CONV,SAT,0>',
    'accum': 'ap_ufixed<18,8,RND_CONV,SAT,0>',
}
out = REPO / 'notebooks' / 'hls4ml_prj_v19_gapufix_tmp'
hm = hls4ml.converters.convert_from_keras_model(
    gap, hls_config=cfg, output_dir=str(out),
    backend='Vivado', io_type='io_stream', part='xczu4ev-sfvc784-1-i', clock_period=5,
)
hm.compile()
result_line = [l for l in (out / 'firmware/defines.h').read_text().splitlines() if ' result_t;' in l][-1]
os.environ['DENSE_NPZ'] = str(REPO / 'deploy/dense_head.npz')
data = np.load(REPO / 'deploy/cifar10_bench.npz', allow_pickle=True)
correct = 0
for i in range(100):
    raw = bytes(data['payloads'][i])
    x = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 1024.0
    x = x.reshape(1, 32, 32, 3)
    hp = np.ravel(hm.predict(np.ascontiguousarray(x)))[:24]
    if int(np.argmax(apply_ps_dense(hp))) == int(data['labels'][i]):
        correct += 1
print(json.dumps({'result_t': result_line.strip(), 'top1': correct}, indent=2))
