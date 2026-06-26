#!/usr/bin/env python3
"""Compare exported AXI csim GAP vs Keras gap layer (same bench inputs)."""
import json
import os
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
HLS_DIR = REPO / 'notebooks' / 'hls4ml_prj'
TB = HLS_DIR / 'tb_data'
MODEL_H5 = REPO / 'notebooks' / 'model_int8_qkeras.h5'
NPZ = REPO / 'deploy' / 'cifar10_bench.npz'
OUT_JSON = REPO / 'results' / 'gap_csim_keras_align.json'

N = int(os.environ.get('N_GAP_COMPARE', '10'))
IN_SCALE = int(os.environ.get('IN_FIXED_SCALE', '1024'))
GAP_DIM = int(os.environ.get('OUT_DIM', '24'))


def load_keras_gap():
    from tensorflow import keras
    import tensorflow as tf
    from qkeras import QActivation, QConv2D, QDense, quantized_bits, quantized_relu

    custom = {
        'QConv2D': QConv2D, 'QDense': QDense, 'QActivation': QActivation,
        'quantized_bits': quantized_bits, 'quantized_relu': quantized_relu,
    }
    model = keras.models.load_model(str(MODEL_H5), custom_objects=custom, compile=False)
    return tf.keras.Model(model.input, model.get_layer('gap').output, name='gap_only')


def load_csim(n):
    path = TB / 'csim_results.log'
    if not path.is_file():
        raise FileNotFoundError('missing %s — run run_gap_axi_csim.sh first' % path)
    lines = path.read_text(encoding='utf-8').strip().splitlines()
    if len(lines) < n:
        raise RuntimeError('csim has %d lines, need %d' % (len(lines), n))
    return [[float(x) for x in ln.split()] for ln in lines[:n]]


def compare_vectors(a, b):
    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    diff = a - b
    return {
        'mae': float(np.mean(np.abs(diff))),
        'max_abs': float(np.max(np.abs(diff))),
        'corr': float(np.corrcoef(a, b)[0, 1]) if np.std(a) > 0 and np.std(b) > 0 else None,
    }


def main():
    if not NPZ.is_file():
        print('ERROR: missing %s' % NPZ, file=sys.stderr)
        return 1

    classes = [
        'airplane', 'automobile', 'bird', 'cat', 'deer',
        'dog', 'frog', 'horse', 'ship', 'truck',
    ]
    data = np.load(NPZ, allow_pickle=True)
    n = min(N, len(data['payloads']))
    csim_gaps = load_csim(n)
    gap_model = load_keras_gap()

    samples = []
    maes = []
    for i in range(n):
        raw = bytes(data['payloads'][i])
        x = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / float(IN_SCALE)
        x = x.reshape(1, 32, 32, 3)
        keras_gap = np.ravel(gap_model.predict(x, verbose=0))[:GAP_DIM]
        csim_gap = np.asarray(csim_gaps[i][:GAP_DIM], dtype=np.float64)
        cmp = compare_vectors(csim_gap, keras_gap)
        maes.append(cmp['mae'])
        samples.append({
            'sample': i,
            'label': classes[int(data['labels'][i])],
            'csim_vs_keras': cmp,
            'keras_gap': [round(float(v), 6) for v in keras_gap],
            'csim_gap': [round(float(v), 6) for v in csim_gap],
        })

    report = {
        'n_samples': n,
        'in_scale': IN_SCALE,
        'gap_dim': GAP_DIM,
        'summary': {
            'csim_vs_keras_mae_mean': float(np.mean(maes)),
            'csim_vs_keras_mae_max': float(np.max(maes)),
        },
        'target_mae': 0.3,
        'pass': float(np.mean(maes)) < 0.3,
        'samples': samples,
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report['summary'], indent=2))
    print('pass (mae<0.3):', report['pass'])
    print('written:', OUT_JSON)
    return 0 if report['pass'] else 1


if __name__ == '__main__':
    sys.exit(main())
