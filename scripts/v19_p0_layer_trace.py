#!/usr/bin/env python3
"""
P0-2: hls4ml layer trace — official hls_model.trace() + Keras reference.

Route 1: bit_exact config from v19_hls_config_common, model from h5.
BN mapping: bn→bn (hls4ml 1.x exposes both conv* and bn_conv*).
"""
import json
import os
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
NPZ = REPO / 'deploy' / 'cifar10_bench.npz'
HLS_PRJ = REPO / 'notebooks' / 'hls4ml_prj'
OUT_JSON = REPO / 'results' / 'v19_p0_layer_trace.json'
OUT_MD = REPO / 'results' / 'v19_p0_layer_trace.md'

sys.path.insert(0, str(REPO / 'scripts'))
from v19_hls_config_common import convert_trace_model, load_gap_model  # noqa: E402

N = int(os.environ.get('N_TRACE', '5'))
IN_SCALE = int(os.environ.get('IN_FIXED_SCALE', '1024'))
GAP_DIM = int(os.environ.get('OUT_DIM', '24'))
MAE_THRESH = float(os.environ.get('TRACE_MAE_THRESH', '0.05'))

KERAS_TO_HLS = [
    ('input_image', 'input_image'),
    ('input_qact', 'input_qact'),
    ('bn_conv1a', 'bn_conv1a'),
    ('bn_conv1b', 'bn_conv1b'),
    ('bn_conv2a', 'bn_conv2a'),
    ('bn_conv2b', 'bn_conv2b'),
    ('bn_conv3a', 'bn_conv3a'),
    ('bn_conv3b', 'bn_conv3b'),
    ('qact_conv1a', 'qact_conv1a'),
    ('qact_conv1b', 'qact_conv1b'),
    ('qact_conv2a', 'qact_conv2a'),
    ('qact_conv2b', 'qact_conv2b'),
    ('qact_conv3a', 'qact_conv3a'),
    ('qact_conv3b', 'qact_conv3b'),
    ('pool1', 'pool1'),
    ('pool2', 'pool2'),
    ('gap', 'gap'),
]


def load_bench(n):
    data = np.load(NPZ, allow_pickle=True)
    n = min(n, len(data['payloads']))
    xs = []
    for i in range(n):
        raw = bytes(data['payloads'][i])
        x = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / float(IN_SCALE)
        xs.append(x.reshape(1, 32, 32, 3))
    return np.vstack(xs)


def flatten_tensor(arr):
    return np.asarray(arr, dtype=np.float64).ravel()


def layer_mae(a, b):
    a = flatten_tensor(a)
    b = flatten_tensor(b)
    n = min(len(a), len(b))
    if n == 0:
        return None
    return float(np.mean(np.abs(a[:n] - b[:n])))


def keras_trace_manual(gap_model, x):
    import tensorflow as tf

    out = {}
    for layer in gap_model.layers:
        try:
            sub = tf.keras.Model(gap_model.input, layer.output, name='kt_' + layer.name)
        except Exception:
            continue
        out[layer.name] = sub.predict(x, verbose=0)
    return out


def main() -> int:
    if not NPZ.is_file():
        print('ERROR: missing bench npz', file=sys.stderr)
        return 1

    gap_model = load_gap_model()
    x = load_bench(1)

    tmp = REPO / 'notebooks' / 'hls4ml_prj_v19_trace_tmp'
    print('convert gap-only (bit_exact) ->', tmp)
    hls_model, hls_config = convert_trace_model(gap_model, tmp, trace=True)
    print('bit_exact:', hls_config.get('BackendConfig', {}).get('bit_exact'))

    print('hls4ml.trace (official, Trace=True)...')
    _, hls_trace = hls_model.trace(np.ascontiguousarray(x))
    if not hls_trace:
        print('WARN: hls_trace empty — check Trace=True in config', file=sys.stderr)
    else:
        print('hls_trace keys (%d):' % len(hls_trace), sorted(hls_trace.keys())[:12], '...')

    print('keras manual trace (QKeras workaround)...')
    keras_trace = keras_trace_manual(gap_model, x)

    rows = []
    first_bad = None
    for keras_layer, hls_layer in KERAS_TO_HLS:
        if keras_layer not in keras_trace:
            continue
        if hls_layer not in hls_trace:
            rows.append({
                'keras_layer': keras_layer,
                'hls_layer': hls_layer,
                'mae': None,
                'note': 'missing in hls trace',
            })
            if first_bad is None and keras_layer != 'input_image':
                first_bad = rows[-1]
            continue
        mae = layer_mae(keras_trace[keras_layer], hls_trace[hls_layer])
        row = {
            'keras_layer': keras_layer,
            'hls_layer': hls_layer,
            'mae': mae,
            'keras_abs_max': float(np.max(np.abs(flatten_tensor(keras_trace[keras_layer])))),
            'hls_abs_max': float(np.max(np.abs(flatten_tensor(hls_trace[hls_layer])))),
        }
        rows.append(row)
        if mae is not None and mae > MAE_THRESH and first_bad is None:
            first_bad = row

    hls_pred = np.ravel(hls_model.predict(np.ascontiguousarray(x)))[:GAP_DIM]
    kg = flatten_tensor(keras_trace['gap'])[:GAP_DIM]
    gap_predict_mae = layer_mae(hls_pred, kg)

    csim_path = HLS_PRJ / 'tb_data' / 'csim_results.log'
    csim_gap_mae = None
    csim_vs_hls_mae = None
    if csim_path.is_file():
        line = csim_path.read_text(encoding='utf-8').strip().splitlines()[0]
        csim = np.array([float(v) for v in line.split()[:GAP_DIM]], dtype=np.float64)
        csim_gap_mae = layer_mae(csim, kg)
        csim_vs_hls_mae = layer_mae(csim, hls_pred)

    report = {
        'route': 'route1_bitexact_trace',
        'n_samples': 1,
        'mae_threshold': MAE_THRESH,
        'method': {
            'hls': 'hls_model.trace() + bit_exact config (v19_hls_config_common)',
            'keras': 'manual submodels from model_int8_qkeras.h5',
            'bn_fusion': 'Keras bn_* vs HLS bn_* (bn→bn)',
        },
        'layer_mae': rows,
        'first_mae_gt_threshold': first_bad,
        'gap_keras_vs_hls_predict_mae': gap_predict_mae,
        'gap_keras_vs_csim_mae_sample0': csim_gap_mae,
        'gap_hls_predict_vs_csim_mae_sample0': csim_vs_hls_mae,
        'hls_trace_layers': sorted(hls_trace.keys()) if hls_trace else [],
        'trace_enabled': True,
    }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(report, indent=2), encoding='utf-8')

    lines = [
        '# v19 P0-2 layer trace (Route 1 bit_exact)',
        '',
        '| Keras | HLS | MAE | Keras abs_max | HLS abs_max |',
        '|---|---|---:|---:|---:|',
    ]
    for r in rows:
        lines.append('| %s | %s | %s | %s | %s |' % (
            r['keras_layer'], r.get('hls_layer', '-'),
            r.get('mae'), r.get('keras_abs_max'), r.get('hls_abs_max')))
    lines.extend([
        '',
        '- GAP keras vs hls predict MAE: **%.4f**' % gap_predict_mae,
    ])
    if csim_gap_mae is not None:
        lines.append('- GAP keras vs exported csim MAE: **%.4f**' % csim_gap_mae)
        lines.append('- GAP hls predict vs exported csim MAE: **%.4f**' % csim_vs_hls_mae)
    if first_bad and first_bad.get('mae') is not None:
        lines.append('- **First layer MAE>%.2f:** `%s` (Keras) vs `%s` (HLS) MAE=%.4f' % (
            MAE_THRESH, first_bad['keras_layer'], first_bad['hls_layer'], first_bad['mae']))
    elif first_bad:
        lines.append('- **First missing layer:** `%s` → `%s`' % (
            first_bad['keras_layer'], first_bad.get('hls_layer', '-')))
    OUT_MD.write_text('\n'.join(lines) + '\n', encoding='utf-8')

    print(json.dumps({
        'first_bad': first_bad,
        'gap_predict_mae': gap_predict_mae,
        'csim_gap_mae': csim_gap_mae,
        'csim_vs_hls_mae': csim_vs_hls_mae,
    }, indent=2))
    print('written: %s' % OUT_JSON)
    print('written: %s' % OUT_MD)
    return 0


if __name__ == '__main__':
    sys.exit(main())
