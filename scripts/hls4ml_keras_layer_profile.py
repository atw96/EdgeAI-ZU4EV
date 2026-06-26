#!/usr/bin/env python3
"""Keras layer activation profiling for hls4ml precision tuning (experiment C')."""
import json
import os
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
MODEL_H5 = REPO / 'notebooks' / 'model_int8_qkeras.h5'
NPZ = REPO / 'deploy' / 'cifar10_bench.npz'
OUT_JSON = REPO / 'results' / 'hls4ml_precision_profile.json'
OUT_MD = REPO / 'results' / 'hls4ml_precision_profile.md'
N = int(os.environ.get('N_PROFILE', '100'))
IN_SCALE = int(os.environ.get('IN_FIXED_SCALE', '1024'))


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


def layer_stats(arr):
    a = np.asarray(arr, dtype=np.float64)
    return {
        'min': float(np.min(a)),
        'max': float(np.max(a)),
        'mean': float(np.mean(a)),
        'std': float(np.std(a)),
        'abs_max': float(np.max(np.abs(a))),
        'abs_p99': float(np.percentile(np.abs(a), 99)),
    }


def suggest_bits(abs_max, min_frac=4, min_total=8):
    if abs_max <= 0:
        return {'ap_fixed': 'ap_fixed<8,3>', 'int_bits': 3, 'total_bits': 8}
    int_bits = max(2, int(np.ceil(np.log2(abs_max + 1e-12))) + 1)
    frac_bits = max(min_frac, min_total - int_bits)
    total = int_bits + frac_bits
    total = max(min_total, total)
    int_bits = total - frac_bits
    return {
        'ap_fixed': 'ap_fixed<%d,%d>' % (total, int_bits),
        'int_bits': int_bits,
        'total_bits': total,
        'frac_bits': frac_bits,
    }


def main() -> int:
    if not MODEL_H5.is_file():
        print('ERROR: missing %s' % MODEL_H5, file=sys.stderr)
        return 1
    if not NPZ.is_file():
        print('ERROR: missing %s' % NPZ, file=sys.stderr)
        return 1

    import tensorflow as tf

    model = load_model()
    x = load_inputs(N)

    gap_layer = model.get_layer('gap')
    gap_model = tf.keras.Model(model.input, gap_layer.output, name='to_gap')

    layer_rows = []
    worst_mae = -1.0
    worst_name = None

    for layer in model.layers:
        if layer.name == 'gap':
            continue
        try:
            sub = tf.keras.Model(model.input, layer.output, name='to_' + layer.name)
        except Exception as exc:
            print('WARN: skip layer %s: %s' % (layer.name, exc))
            continue
        y = sub.predict(x, verbose=0)
        st = layer_stats(y)
        sug = suggest_bits(st['abs_p99'])
        row = {
            'layer': layer.name,
            'type': layer.__class__.__name__,
            'stats': st,
            'suggest_result': sug['ap_fixed'],
        }
        layer_rows.append(row)

    gap_keras = gap_model.predict(x, verbose=0)
    gap_stats = layer_stats(gap_keras)
    gap_suggest = suggest_bits(gap_stats['abs_p99'], min_frac=6, min_total=16)

    recommended = {
        'PREC_CONV': {
            'weight': 'ap_fixed<8,2>',
            'bias': 'ap_fixed<8,3>',
            'result': 'ap_fixed<10,4>',
            'accum': 'ap_fixed<16,6>',
        },
        'PREC_BN': {
            'scale': 'ap_fixed<10,4>',
            'bias': 'ap_fixed<10,4>',
            'result': 'ap_fixed<10,4>',
        },
        'PREC_ACT': {'result': 'ap_fixed<10,4>'},
        'PREC_HEAD': {
            'weight': 'ap_fixed<16,8>',
            'bias': 'ap_fixed<16,8>',
            'result': 'ap_fixed<16,8>',
            'accum': 'ap_fixed<16,8>',
        },
        'PREC_GAP': {
            'accum': 'ap_fixed<18,10>',
            'result': 'ap_fixed<16,8>',
        },
        'Model': {'Precision': 'ap_fixed<16,8>'},
    }

    report = {
        'n_samples': int(x.shape[0]),
        'gap_keras_stats': gap_stats,
        'gap_suggest_result': gap_suggest['ap_fixed'],
        'gap_suggest_accum': 'ap_fixed<18,10>',
        'layers': layer_rows,
        'recommended_precision': recommended,
        'notes': [
            'Conv/BN widened from ap_fixed<6,3> per hls4ml profiling guidance',
            'GAP accum widened (hls4ml issue #1297 avgpool truncation)',
            'RF/partition unchanged — literature: RF does not affect accuracy',
        ],
    }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(report, indent=2), encoding='utf-8')

    lines = [
        '# hls4ml precision profile (experiment C\')',
        '',
        'Samples: %d' % report['n_samples'],
        '',
        '## GAP (Keras reference)',
        '- abs_max: %.6f' % gap_stats['abs_max'],
        '- suggest result: %s' % gap_suggest['ap_fixed'],
        '- recommend accum: ap_fixed<18,10>',
        '',
        '## Layer activation ranges (top 8 by abs_max)',
    ]
    top = sorted(layer_rows, key=lambda r: r['stats']['abs_max'], reverse=True)[:8]
    for r in top:
        lines.append(
            '- %s (%s): abs_max=%.4f suggest=%s'
            % (r['layer'], r['type'], r['stats']['abs_max'], r['suggest_result'])
        )
    lines.extend(['', 'Written: %s' % OUT_JSON])
    OUT_MD.write_text('\n'.join(lines) + '\n', encoding='utf-8')

    print('Wrote %s' % OUT_JSON)
    print('Wrote %s' % OUT_MD)
    print('GAP abs_max=%.4f recommend accum=ap_fixed<18,10> result=ap_fixed<16,8>' % (
        gap_stats['abs_max']))
    return 0


if __name__ == '__main__':
    sys.exit(main())
