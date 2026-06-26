#!/usr/bin/env python3
"""Verify Q6 QKeras model accuracy on deploy/cifar10_bench.npz."""
import json
import os
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
MODEL_H5 = REPO / 'notebooks' / 'model_int8_qkeras.h5'
NPZ = REPO / 'deploy' / 'cifar10_bench.npz'
DENSE_NPZ = REPO / 'deploy' / 'dense_head.npz'
OUT_JSON = REPO / 'results' / 'v19_q6_bench_verify.json'
IN_SCALE = int(os.environ.get('IN_FIXED_SCALE', '1024'))
N = int(os.environ.get('N_ACCURACY', '100'))


def load_inputs(n):
    data = np.load(NPZ, allow_pickle=True)
    n = min(n, len(data['payloads']))
    xs, ys = [], []
    for i in range(n):
        raw = bytes(data['payloads'][i])
        x = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / float(IN_SCALE)
        xs.append(x.reshape(32, 32, 3))
        ys.append(int(data['labels'][i]))
    return np.stack(xs), np.array(ys, dtype=np.int64)


def load_model():
    from tensorflow import keras
    from qkeras import QActivation, QConv2D, QDense, quantized_bits, quantized_relu

    custom = {
        'QConv2D': QConv2D, 'QDense': QDense, 'QActivation': QActivation,
        'quantized_bits': quantized_bits, 'quantized_relu': quantized_relu,
    }
    return keras.models.load_model(str(MODEL_H5), custom_objects=custom, compile=False)


def top1_pct(y_true, y_pred):
    return 100.0 * float(np.mean(y_true == y_pred))


def main() -> int:
    if not MODEL_H5.is_file():
        print('ERROR: missing %s' % MODEL_H5, file=sys.stderr)
        return 1
    if not NPZ.is_file():
        print('ERROR: missing %s' % NPZ, file=sys.stderr)
        return 1

    import tensorflow as tf

    model = load_model()
    x, y = load_inputs(N)

    y_full = np.argmax(model.predict(x, verbose=0, batch_size=32), axis=1)
    gap_model = tf.keras.Model(model.input, model.get_layer('gap').output)
    gap = gap_model.predict(x, verbose=0, batch_size=32)

    dense_top1 = None
    if DENSE_NPZ.is_file():
        dh = np.load(DENSE_NPZ)
        logits = gap @ dh['weight'] + dh['bias']
        dense_top1 = top1_pct(y, np.argmax(logits, axis=1))

    report = {
        'n_samples': int(len(y)),
        'full_model_top1_pct': top1_pct(y, y_full),
        'gap_ps_dense_top1_pct': dense_top1,
        'gap_stats': {
            'min': float(np.min(gap)),
            'max': float(np.max(gap)),
            'mean': float(np.mean(gap)),
            'abs_max': float(np.max(np.abs(gap))),
        },
        'model_h5': str(MODEL_H5),
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))
    print('written: %s' % OUT_JSON)
    return 0


if __name__ == '__main__':
    sys.exit(main())
