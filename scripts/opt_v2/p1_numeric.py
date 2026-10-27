#!/usr/bin/env python3
"""P1 numeric gate on two csim GAP logs and the Q6 Keras model.

Uses the first N rows of CSIM_NPZ (default: CIFAR-10 test order, 1k file).
Does not overwrite an existing gate JSON.
"""
import json
import os
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]


def load_log(path, n):
    lines = Path(path).read_text(encoding='utf-8').strip().splitlines()
    if len(lines) < n:
        raise SystemExit('%s has %d lines, need %d' % (path, len(lines), n))
    rows = [[float(x) for x in line.split()] for line in lines[:n]]
    return lines[:n], np.asarray(rows, dtype=np.float64)


def main():
    n_req = int(os.environ.get('N_GAP_COMPARE', '1000'))
    npz_path = Path(os.environ.get('CSIM_NPZ', str(REPO / 'deploy' / 'cifar10_bench_1k.npz')))
    out = Path(os.environ.get('P1_GATE_JSON', str(REPO / 'results' / 'opt_v2' / 'p1_gate.json')))
    if out.exists():
        print('ERROR: refuse to overwrite %s' % out, file=sys.stderr)
        return 1
    log_a = Path(sys.argv[1])
    log_b = Path(sys.argv[2])
    data = np.load(npz_path, allow_pickle=True)
    n = min(n_req, len(data['payloads']), len(data['labels']))
    text_a, gap_a = load_log(log_a, n)
    text_b, gap_b = load_log(log_b, n)
    text_equal = text_a == text_b
    max_abs_ab = float(np.max(np.abs(gap_a - gap_b)))

    os.environ.setdefault('PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION', 'python')
    import tensorflow as tf
    from tensorflow import keras
    from qkeras import QActivation, QConv2D, QDense, quantized_bits, quantized_relu

    custom = {
        'QConv2D': QConv2D, 'QDense': QDense, 'QActivation': QActivation,
        'quantized_bits': quantized_bits, 'quantized_relu': quantized_relu,
    }
    model = keras.models.load_model(
        str(REPO / 'notebooks' / 'model_int8_qkeras.h5'),
        custom_objects=custom, compile=False,
    )
    scale = float(os.environ.get('IN_FIXED_SCALE', '1024'))
    xs = []
    ys = []
    for i in range(n):
        raw = bytes(data['payloads'][i])
        xs.append(np.frombuffer(raw, dtype=np.int16).astype(np.float32).reshape(32, 32, 3) / scale)
        ys.append(int(data['labels'][i]))
    x = np.stack(xs)
    y = np.asarray(ys)
    keras_prob = model.predict(x, verbose=0, batch_size=64)
    keras_top = np.argmax(keras_prob, axis=1)
    gap = tf.keras.Model(model.input, model.get_layer('gap').output).predict(
        x, verbose=0, batch_size=64)
    gap = np.asarray(gap, dtype=np.float64)[:, :gap_a.shape[1]]

    def mae(pred):
        diff = np.abs(pred - gap)
        return float(np.mean(diff)), float(np.max(diff))

    mae_a, max_a = mae(gap_a)
    mae_b, max_b = mae(gap_b)
    dense = model.get_layer('predictions')
    weight, bias = dense.get_weights()[:2]
    weight = np.asarray(weight, dtype=np.float64)
    bias = np.asarray(bias, dtype=np.float64)

    def top1(g):
        return np.argmax(g @ weight + bias, axis=1)

    top_a = top1(gap_a)
    top_b = top1(gap_b)
    keras_pct = 100.0 * float(np.mean(keras_top == y))
    a_pct = 100.0 * float(np.mean(top_a == y))
    b_pct = 100.0 * float(np.mean(top_b == y))
    ok = (
        text_equal
        and max_abs_ab == 0.0
        and mae_a <= 0.05
        and mae_b <= 0.05
        and abs(a_pct - keras_pct) <= 1.0
        and abs(b_pct - keras_pct) <= 1.0
    )
    doc = {
        'n': n,
        'npz': str(npz_path),
        'bit_exact': bool(text_equal and max_abs_ab == 0.0),
        'max_abs_p4_vs_a1': max_abs_ab,
        'mae_p4': mae_a,
        'max_abs_p4_vs_keras': max_a,
        'mae_a1': mae_b,
        'max_abs_a1_vs_keras': max_b,
        'top1_keras': keras_pct,
        'top1_p4': a_pct,
        'top1_a1': b_pct,
        'reference_full_test_keras': 81.95,
        'pass': bool(ok),
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2), encoding='utf-8')
    print(json.dumps(doc, indent=2))
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
