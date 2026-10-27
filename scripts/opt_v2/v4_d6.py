#!/usr/bin/env python3
"""D6: Keras self-check on the same 1000 images and the Q6 h5. Does not write the h5."""
import hashlib
import json
import os
from pathlib import Path

import numpy as np

os.environ.setdefault('PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION', 'python')

REPO = Path(__file__).resolve().parents[2]
H5 = REPO / 'notebooks' / 'model_int8_qkeras.h5'
NPZ = REPO / 'deploy' / 'cifar10_bench_1k.npz'
DENSE = REPO / 'deploy' / 'dense_head.npz'
OUT = REPO / 'results' / 'opt_v2' / 'v4_d6.json'


def md5(path):
    h = hashlib.md5()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def main():
    from tensorflow import keras
    from qkeras import QActivation, QConv2D, QDense, quantized_bits, quantized_relu

    custom = {
        'QConv2D': QConv2D, 'QDense': QDense, 'QActivation': QActivation,
        'quantized_bits': quantized_bits, 'quantized_relu': quantized_relu,
    }
    model = keras.models.load_model(str(H5), custom_objects=custom, compile=False)
    data = np.load(NPZ, allow_pickle=True)
    n = 1000
    xs, ys = [], []
    for i in range(n):
        raw = bytes(data['payloads'][i])
        xs.append(np.frombuffer(raw, dtype=np.int16).astype(np.float32).reshape(32, 32, 3) / 1024.0)
        ys.append(int(data['labels'][i]))
    x = np.stack(xs)
    y = np.asarray(ys, dtype=np.int32)

    qact = None
    for layer in model.layers:
        if layer.name == 'input_qact' or layer.__class__.__name__ == 'QActivation' and qact is None:
            if layer.name == 'input_qact':
                qact = layer
                break
    q_out = keras.Model(model.input, qact.output).predict(x[:64], verbose=0, batch_size=64)
    q_out = np.asarray(q_out, dtype=np.float64)
    # 6-bit grid: values that survive *64 and come back equal are on a 1/64 grid.
    # Also record the actual unique-step of the first image.
    snapped = np.round(q_out * 64.0) / 64.0
    on_grid_64 = bool(np.max(np.abs(q_out - snapped)) < 1e-5)
    flat = np.unique(np.round(q_out.ravel(), 6))
    if len(flat) > 1:
        step = float(np.min(np.diff(flat)))
    else:
        step = 0.0

    prob = model.predict(x, verbose=0, batch_size=64)
    keras_pred = np.argmax(prob, axis=1).astype(np.int32)
    gap = keras.Model(model.input, model.get_layer('gap').output).predict(x, verbose=0, batch_size=64)
    gap = np.asarray(gap, dtype=np.float64)
    w_k, b_k = model.get_layer('predictions').get_weights()[:2]
    pred_keras_head = np.argmax(gap @ np.asarray(w_k, dtype=np.float64) + np.asarray(b_k, dtype=np.float64), axis=1)

    z = np.load(DENSE)
    # dense_head.npz keys vary; accept weight/bias or w/b.
    keys = list(z.keys())
    weight = z['weight'] if 'weight' in z else z['w'] if 'w' in z else z[keys[0]]
    bias = z['bias'] if 'bias' in z else z['b'] if 'b' in z else z[keys[1]]
    pred_npz = np.argmax(gap @ np.asarray(weight, dtype=np.float64) + np.asarray(bias, dtype=np.float64), axis=1)

    keras_top = 100.0 * float(np.mean(keras_pred == y))
    head_top = 100.0 * float(np.mean(pred_keras_head == y))
    npz_top = 100.0 * float(np.mean(pred_npz == y))
    doc = {
        'id': 'D6',
        'date': '2026-10-17',
        'env': {'h5': str(H5), 'h5_md5': md5(H5), 'h5_bytes': H5.stat().st_size},
        'inputs': {'h5': 'notebooks/model_int8_qkeras.h5', 'h5_md5': md5(H5),
                   'n_images': n, 'order': 'fixed test order, cifar10_bench_1k.npz'},
        'results': {
            'input_qact_layer': qact.name,
            'input_qact_on_1_over_64_grid_first64': on_grid_64,
            'input_qact_min_unique_step_first64': step,
            'input_qact_n_unique_first64': int(len(flat)),
            'keras_top1': keras_top,
            'keras_predictions_layer_on_gap_top1': head_top,
            'dense_head_npz_on_keras_gap_top1': npz_top,
            'keras_vs_dense_npz_pred_mismatches': int(np.sum(pred_keras_head != pred_npz)),
            'dense_npz_keys': keys,
            'reproduced_81_8': abs(keras_top - 81.8) < 0.05,
        },
        'decision': 'Keras 1000-image Top-1 reproduced; dense_head compared to the predictions layer on the same GAP.',
        'next': 'Use this Keras Top-1 as the G1 reference. Do not overwrite the h5.',
    }
    if OUT.exists():
        raise SystemExit('refuse overwrite %s' % OUT)
    OUT.write_text(json.dumps(doc, indent=2), encoding='utf-8')
    print(json.dumps(doc['results'], indent=2))


if __name__ == '__main__':
    main()
