#!/usr/bin/env python3
"""
QAT-aware hls4ml precision inference from Keras activation profiling.

Uses post-ReLU abs_max (not p99) and enforces Q6-safe minimum bit widths.
"""
import json
import math
import os
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
MODEL_H5 = REPO / 'notebooks' / 'model_int8_qkeras.h5'
NPZ = REPO / 'deploy' / 'cifar10_bench.npz'
OUT_JSON = REPO / 'results' / 'v19_qat_precision.json'
OUT_MD = REPO / 'results' / 'v19_qat_precision.md'
N = int(os.environ.get('N_PROFILE', '200'))
IN_SCALE = int(os.environ.get('IN_FIXED_SCALE', '1024'))


def ap_fixed(total_bits, int_bits):
    total_bits = max(4, int(total_bits))
    int_bits = max(1, min(int_bits, total_bits - 1))
    return 'ap_fixed<%d,%d>' % (total_bits, int_bits)


def bits_for_range(abs_max, min_frac=4, min_total=8, headroom=1):
    if abs_max <= 0:
        return ap_fixed(min_total, min_total - min_frac)
    int_bits = max(2, int(math.ceil(math.log2(abs_max + 1e-9))) + headroom)
    frac_bits = max(min_frac, min_total - int_bits)
    total = max(min_total, int_bits + frac_bits)
    int_bits = total - frac_bits
    return ap_fixed(total, int_bits)


def max_of(rows, key_fn, field='abs_max', default=1.0):
    vals = [key_fn(r) for r in rows if key_fn(r) is not None]
    if not vals:
        return default
    return max(r['stats'][field] for r in rows if key_fn(r) is not None)


def pick_wider(a, b):
    """Return ap_fixed string with larger total bit width."""
    def parse(s):
        m = __import__('re').search(r'ap_fixed<(\d+),(\d+)>', s)
        return (int(m.group(1)), int(m.group(2))) if m else (0, 0)

    wa, wb = parse(a), parse(b)
    return a if wa[0] >= wb[0] else b


def layer_stats(arr):
    a = np.asarray(arr, dtype=np.float64)
    return {
        'min': float(np.min(a)),
        'max': float(np.max(a)),
        'abs_max': float(np.max(np.abs(a))),
        'abs_p99': float(np.percentile(np.abs(a), 99)),
    }


def load_model():
    from tensorflow import keras
    from qkeras import QActivation, QConv2D, QDense, quantized_bits, quantized_relu

    custom = {
        'QConv2D': QConv2D, 'QDense': QDense, 'QActivation': QActivation,
        'quantized_bits': quantized_bits, 'quantized_relu': quantized_relu,
    }
    return keras.models.load_model(str(MODEL_H5), custom_objects=custom, compile=False)


def load_inputs(n):
    data = np.load(NPZ, allow_pickle=True)
    n = min(n, len(data['payloads']))
    xs = []
    for i in range(n):
        raw = bytes(data['payloads'][i])
        x = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / float(IN_SCALE)
        xs.append(x.reshape(1, 32, 32, 3))
    return np.vstack(xs)


def main() -> int:
    if not MODEL_H5.is_file() or not NPZ.is_file():
        print('ERROR: missing model or bench npz', file=sys.stderr)
        return 1

    import tensorflow as tf

    model = load_model()
    x = load_inputs(N)

    layer_rows = []
    for layer in model.layers:
        try:
            sub = tf.keras.Model(model.input, layer.output, name='to_' + layer.name)
        except Exception as exc:
            print('WARN: skip %s: %s' % (layer.name, exc))
            continue
        y = sub.predict(x, verbose=0)
        st = layer_stats(y)
        layer_rows.append({
            'layer': layer.name,
            'type': layer.__class__.__name__,
            'stats': st,
        })

    gap_model = tf.keras.Model(model.input, model.get_layer('gap').output)
    gap_y = gap_model.predict(x, verbose=0)
    gap_st = layer_stats(gap_y)

    # Post-ReLU ranges drive conv/act result types (QAT deploy path).
    relu_max = max_of(layer_rows, lambda r: r if 'relu' in r['layer'] else None)
    bn_max = max_of(layer_rows, lambda r: r if r['layer'].startswith('bn_') else None)
    pool_max = max_of(layer_rows, lambda r: r if 'pool' in r['layer'] else None, default=2.0)

    conv_result = pick_wider(
        bits_for_range(relu_max, min_frac=4, min_total=10, headroom=2),
        ap_fixed(10, 4),
    )
    bn_result = pick_wider(
        bits_for_range(bn_max, min_frac=4, min_total=10, headroom=2),
        ap_fixed(10, 4),
    )
    act_result = pick_wider(
        bits_for_range(relu_max, min_frac=4, min_total=8, headroom=1),
        ap_fixed(10, 4),
    )
    gap_result = pick_wider(
        bits_for_range(gap_st['abs_max'], min_frac=6, min_total=16, headroom=2),
        ap_fixed(16, 8),
    )
    conv_accum = pick_wider(bits_for_range(relu_max * 8, min_frac=6, min_total=16, headroom=2), ap_fixed(16, 6))
    gap_accum = pick_wider(bits_for_range(gap_st['abs_max'] * 64, min_frac=8, min_total=18, headroom=2), ap_fixed(18, 10))

    recommended = {
        'PREC_CONV': {
            'weight': ap_fixed(8, 2),
            'bias': ap_fixed(8, 3),
            'result': conv_result,
            'accum': conv_accum,
        },
        'PREC_BN': {
            'scale': bn_result,
            'bias': bn_result,
            'result': bn_result,
        },
        'PREC_ACT': {'result': act_result},
        'PREC_DENSE': {
            'weight': ap_fixed(16, 8),
            'bias': ap_fixed(16, 8),
            'result': ap_fixed(16, 8),
            'accum': ap_fixed(16, 8),
        },
        'PREC_HEAD': {
            'weight': ap_fixed(16, 8),
            'bias': ap_fixed(16, 8),
            'result': ap_fixed(16, 8),
            'accum': ap_fixed(16, 8),
        },
        'PREC_GAP': {
            'accum': gap_accum,
            'result': gap_result,
        },
        'Model': {
            'Precision': gap_result,
            'InputPrecision': ap_fixed(16, 6),
        },
    }

    report = {
        'n_samples': int(x.shape[0]),
        'gap_keras_stats': gap_st,
        'relu_abs_max': relu_max,
        'bn_abs_max': bn_max,
        'layers': layer_rows,
        'recommended_precision': recommended,
        'notes': [
            'Use post-ReLU abs_max (not p99) for conv/act — fixes ap_fixed<8,2> zero-output bug',
            'GAP result min ap_fixed<16,8>, accum min ap_fixed<18,10>',
        ],
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(report, indent=2), encoding='utf-8')
    OUT_MD.write_text(
        '# v19 QAT precision (fixed)\n\nrelu_max=%.4f\nconv=%s\ngap=%s accum=%s\n'
        % (relu_max, conv_result, gap_result, gap_accum),
        encoding='utf-8',
    )
    print('Wrote %s' % OUT_JSON)
    print('relu_abs_max=%.4f conv=%s gap=%s accum=%s' % (relu_max, conv_result, gap_result, gap_accum))
    return 0


if __name__ == '__main__':
    sys.exit(main())
