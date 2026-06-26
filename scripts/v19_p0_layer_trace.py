#!/usr/bin/env python3
"""
P0-2: hls4ml layer trace — official hls_model.trace() + Keras reference.

Refs:
  - https://fastmachinelearning.org/hls4ml/api/HLS-MODEL.html (trace API)
  - https://github.com/fastmachinelearning/hls4ml/blob/main/docs/advanced/profiling.rst
    (BN fused into conv: compare Keras bn_* output to HLS conv* output)
  - https://github.com/fastmachinelearning/hls4ml/issues/265
    (get_ymodel_keras fails on QKeras in older hls4ml — use manual Keras submodels)
"""
import json
import os
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
NB = REPO / 'notebooks' / 'cifar10_hls4ml_synthesis.ipynb'
NPZ = REPO / 'deploy' / 'cifar10_bench.npz'
HLS_PRJ = REPO / 'notebooks' / 'hls4ml_prj'
OUT_JSON = REPO / 'results' / 'v19_p0_layer_trace.json'
OUT_MD = REPO / 'results' / 'v19_p0_layer_trace.md'
N = int(os.environ.get('N_TRACE', '5'))
IN_SCALE = int(os.environ.get('IN_FIXED_SCALE', '1024'))
MAE_THRESH = float(os.environ.get('TRACE_MAE_THRESH', '0.05'))

# hls4ml 1.x trace exposes both conv* and bn_conv*; prefer bn→bn when present.
KERAS_TO_HLS = {
    'input_image': 'input_image',
    'bn_conv1a': 'bn_conv1a',
    'bn_conv1b': 'bn_conv1b',
    'bn_conv2a': 'bn_conv2a',
    'bn_conv2b': 'bn_conv2b',
    'bn_conv3a': 'bn_conv3a',
    'bn_conv3b': 'bn_conv3b',
    'relu_conv1a': 'relu_conv1a',
    'relu_conv1b': 'relu_conv1b',
    'relu_conv2a': 'relu_conv2a',
    'relu_conv2b': 'relu_conv2b',
    'relu_conv3a': 'relu_conv3a',
    'relu_conv3b': 'relu_conv3b',
    'pool1': 'pool1',
    'pool2': 'pool2',
    'gap': 'gap',
}


def load_bench(n):
    data = np.load(NPZ, allow_pickle=True)
    n = min(n, len(data['payloads']))
    xs = []
    for i in range(n):
        raw = bytes(data['payloads'][i])
        x = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / float(IN_SCALE)
        xs.append(x.reshape(1, 32, 32, 3))
    return np.vstack(xs)


def build_hls_config_and_gap_model():
    import json as _json
    import os as _os

    nb = _json.loads(NB.read_text(encoding='utf-8'))
    _os.chdir(REPO / 'notebooks')
    g = {'__name__': '__main__', '__file__': str(NB)}
    for idx in (2, 4, 6):
        exec(compile(''.join(nb['cells'][idx]['source']), str(NB) + ':%d' % idx, 'exec'), g)
    import tensorflow as tf
    model = g['model']
    gap_model = tf.keras.Model(
        inputs=model.input,
        outputs=model.get_layer('gap').output,
        name=model.name + '_gaponly',
    )
    return gap_model, g['hls_config']


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
    """Keras per-layer outputs (QKeras workaround when get_ymodel_keras fails)."""
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
    if not NPZ.is_file() or not NB.is_file():
        print('ERROR: missing bench npz or notebook', file=sys.stderr)
        return 1

    import hls4ml

    gap_model, hls_config = build_hls_config_and_gap_model()
    x = load_bench(1)

    # Tutorial Part 2: enable Trace before convert
    # https://github.com/fastmachinelearning/hls4ml-tutorial/blob/master/part2_advanced_config.ipynb
    for lname in list(hls_config.get('LayerName', {}).keys()):
        hls_config['LayerName'][lname].setdefault('Trace', True)
        hls_config['LayerName'][lname]['Trace'] = True

    tmp = REPO / 'notebooks' / 'hls4ml_prj_v19_trace_tmp'
    print('convert gap-only ->', tmp)
    hls_model = hls4ml.converters.convert_from_keras_model(
        gap_model,
        hls_config=hls_config,
        output_dir=str(tmp),
        backend='Vivado',
        io_type='io_stream',
        part='xczu4ev-sfvc784-1-i',
        clock_period=5,
    )
    hls_model.compile()

    print('hls4ml.trace (official, Trace=True per tutorial)...')
    _, hls_trace = hls_model.trace(np.ascontiguousarray(x))
    if not hls_trace:
        print('WARN: hls_trace empty — check Trace=True in config', file=sys.stderr)
    else:
        print('hls_trace keys (%d):' % len(hls_trace), sorted(hls_trace.keys())[:12], '...')

    print('keras manual trace (QKeras / Issue #265 workaround)...')
    keras_trace = keras_trace_manual(gap_model, x)

    rows = []
    first_bad = None
    for keras_layer, hls_layer in KERAS_TO_HLS.items():
        if keras_layer not in keras_trace:
            continue
        if hls_layer not in hls_trace:
            rows.append({
                'keras_layer': keras_layer,
                'hls_layer': hls_layer,
                'mae': None,
                'note': 'missing in hls trace',
            })
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

    # hls predict vs keras at gap
    hls_pred = np.ravel(hls_model.predict(np.ascontiguousarray(x)))[:24]
    kg = flatten_tensor(keras_trace['gap'])[:24]
    gap_predict_mae = layer_mae(hls_pred, kg)

    # exported firmware csim vs keras / hls predict
    csim_path = HLS_PRJ / 'tb_data' / 'csim_results.log'
    csim_gap_mae = None
    csim_vs_hls_mae = None
    if csim_path.is_file():
        line = csim_path.read_text(encoding='utf-8').strip().splitlines()[0]
        csim = np.array([float(v) for v in line.split()[:24]], dtype=np.float64)
        csim_gap_mae = layer_mae(csim, kg)
        csim_vs_hls_mae = layer_mae(csim, hls_pred)

    report = {
        'n_samples': 1,
        'mae_threshold': MAE_THRESH,
        'method': {
            'hls': 'hls_model.trace() per HLS Model docs',
            'keras': 'manual submodels (get_ymodel_keras broken on QKeras 0.8.1, issue #265)',
            'bn_fusion': 'Keras bn_* compared to HLS conv* per profiling.rst',
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
        '# v19 P0-2 layer trace',
        '',
        'Refs: [HLS Model trace](https://fastmachinelearning.org/hls4ml/api/HLS-MODEL.html), '
        '[profiling.rst BN fusion](https://github.com/fastmachinelearning/hls4ml/blob/main/docs/advanced/profiling.rst), '
        '[Issue #265 QKeras profiling](https://github.com/fastmachinelearning/hls4ml/issues/265)',
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
    if first_bad:
        lines.append('- **First layer MAE>%.2f:** `%s` (Keras) vs `%s` (HLS) MAE=%.4f' % (
            MAE_THRESH, first_bad['keras_layer'], first_bad['hls_layer'], first_bad['mae']))
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
