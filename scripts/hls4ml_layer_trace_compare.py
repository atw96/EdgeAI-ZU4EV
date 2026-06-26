#!/usr/bin/env python3
"""Keras vs HLS layer-wise MAE trace (post-convert firmware predict if available)."""
import json
import os
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
MODEL_H5 = REPO / 'notebooks' / 'model_int8_qkeras.h5'
NPZ = REPO / 'deploy' / 'cifar10_bench.npz'
HLS_DIR = REPO / 'notebooks' / 'hls4ml_prj'
OUT_JSON = REPO / 'results' / 'v19_layer_trace.json'
N = int(os.environ.get('N_TRACE', '20'))
IN_SCALE = int(os.environ.get('IN_FIXED_SCALE', '1024'))


def load_inputs(n):
    data = np.load(NPZ, allow_pickle=True)
    n = min(n, len(data['payloads']))
    xs = []
    for i in range(n):
        raw = bytes(data['payloads'][i])
        x = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / float(IN_SCALE)
        xs.append(x.reshape(1, 32, 32, 3))
    return np.vstack(xs)


def load_keras_model():
    from tensorflow import keras
    from qkeras import QActivation, QConv2D, QDense, quantized_bits, quantized_relu

    custom = {
        'QConv2D': QConv2D, 'QDense': QDense, 'QActivation': QActivation,
        'quantized_bits': quantized_bits, 'quantized_relu': quantized_relu,
    }
    return keras.models.load_model(str(MODEL_H5), custom_objects=custom, compile=False)


def keras_layer_mae(model, x):
    import tensorflow as tf

    rows = []
    for layer in model.layers:
        if layer.name in ('input_image', 'predictions', 'predictions_logits'):
            continue
        try:
            sub = tf.keras.Model(model.input, layer.output, name='trace_' + layer.name)
        except Exception:
            continue
        y = sub.predict(x, verbose=0)
        rows.append({
            'layer': layer.name,
            'type': layer.__class__.__name__,
            'out_shape': list(y.shape),
            'abs_max': float(np.max(np.abs(y))),
        })
    return rows


def hls_gap_mae_from_csim():
    tb = HLS_DIR / 'tb_data' / 'csim_results.log'
    if not tb.is_file():
        return None
    return {'source': 'csim_gap_only', 'path': str(tb)}


def main() -> int:
    if not MODEL_H5.is_file() or not NPZ.is_file():
        print('ERROR: missing model or npz', file=sys.stderr)
        return 1

    import tensorflow as tf

    model = load_keras_model()
    x = load_inputs(N)
    keras_rows = keras_layer_mae(model, x)

    gap_k = tf.keras.Model(model.input, model.get_layer('gap').output)
    gap_ref = gap_k.predict(x, verbose=0)

    hls_note = hls_gap_mae_from_csim()
    csim_mae = None
    if hls_note:
        lines = Path(hls_note['path']).read_text(encoding='utf-8').strip().splitlines()
        n = min(N, len(lines))
        maes = []
        for i in range(n):
            csim = np.array([float(v) for v in lines[i].split()[:24]], dtype=np.float64)
            ref = np.ravel(gap_ref[i])[:24]
            maes.append(float(np.mean(np.abs(csim - ref))))
        csim_mae = float(np.mean(maes))

    report = {
        'n_samples': int(x.shape[0]),
        'keras_layers': keras_rows,
        'gap_csim_mae_mean': csim_mae,
        'gap_keras_abs_max': float(np.max(np.abs(gap_ref))),
        'first_large_layer': next(
            (r for r in keras_rows if r['abs_max'] > 8.0),
            None,
        ),
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({'gap_csim_mae_mean': csim_mae, 'n_layers': len(keras_rows)}, indent=2))
    print('written: %s' % OUT_JSON)
    return 0


if __name__ == '__main__':
    sys.exit(main())
