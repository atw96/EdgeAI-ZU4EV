#!/usr/bin/env python3
"""
Deep layer alignment: Keras vs hls4ml trace vs csim GAP.

Tests BN fusion mappings (profiling.rst: Keras bn_* vs HLS conv*),
auto-discovers best HLS partner per Keras layer, and tri-compares GAP.
"""
import json
import os
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
NB = REPO / 'notebooks' / 'cifar10_hls4ml_synthesis.ipynb'
MODEL_H5 = REPO / 'notebooks' / 'model_int8_qkeras.h5'
NPZ = REPO / 'deploy' / 'cifar10_bench.npz'
HLS_PRJ = REPO / 'notebooks' / 'hls4ml_prj'
OUT_JSON = REPO / 'results' / 'v19_csim_keras_layer_align.json'
OUT_MD = REPO / 'results' / 'v19_csim_keras_layer_align.md'

N = int(os.environ.get('N_ALIGN', '20'))
IN_SCALE = int(os.environ.get('IN_FIXED_SCALE', '1024'))
GAP_DIM = int(os.environ.get('OUT_DIM', '24'))
MAE_THRESH = float(os.environ.get('TRACE_MAE_THRESH', '0.05'))

# Default fusion map per hls4ml profiling.rst
# hls4ml 1.x trace lists both conv* and bn_conv*; compare bn→bn (not bn→conv).
FUSION_MAP = {
    'bn_conv1a': 'bn_conv1a',
    'bn_conv1b': 'bn_conv1b',
    'bn_conv2a': 'bn_conv2a',
    'bn_conv2b': 'bn_conv2b',
    'bn_conv3a': 'bn_conv3a',
    'bn_conv3b': 'bn_conv3b',
}

KERAS_LAYER_ORDER = [
    'input_image',
    'conv1a', 'bn_conv1a', 'relu_conv1a',
    'conv1b', 'bn_conv1b', 'relu_conv1b', 'pool1',
    'conv2a', 'bn_conv2a', 'relu_conv2a',
    'conv2b', 'bn_conv2b', 'relu_conv2b', 'pool2',
    'conv3a', 'bn_conv3a', 'relu_conv3a',
    'conv3b', 'bn_conv3b', 'relu_conv3b',
    'gap',
]


def load_bench(n):
    data = np.load(NPZ, allow_pickle=True)
    n = min(n, len(data['payloads']))
    xs, labels = [], []
    for i in range(n):
        raw = bytes(data['payloads'][i])
        x = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / float(IN_SCALE)
        xs.append(x.reshape(1, 32, 32, 3))
        labels.append(int(data['labels'][i]))
    return np.vstack(xs), labels


def load_gap_model():
    import tensorflow as tf
    from qkeras import QActivation, QConv2D, QDense, quantized_bits, quantized_relu

    custom = {
        'QConv2D': QConv2D, 'QDense': QDense, 'QActivation': QActivation,
        'quantized_bits': quantized_bits, 'quantized_relu': quantized_relu,
    }
    model = tf.keras.models.load_model(str(MODEL_H5), custom_objects=custom, compile=False)
    gap = tf.keras.Model(model.input, model.get_layer('gap').output, name='gaponly')
    return gap


def build_hls_config_from_notebook():
    import json as _json
    import os as _os

    nb = _json.loads(NB.read_text(encoding='utf-8'))
    _os.chdir(REPO / 'notebooks')
    g = {'__name__': '__main__', '__file__': str(NB)}
    for idx in (2, 4, 6):
        exec(compile(''.join(nb['cells'][idx]['source']), str(NB) + ':%d' % idx, 'exec'), g)
    return g['hls_config']


def flatten(arr):
    return np.asarray(arr, dtype=np.float64).ravel()


def vec_stats(a, b):
    a, b = flatten(a), flatten(b)
    n = min(len(a), len(b))
    if n == 0:
        return None
    a, b = a[:n], b[:n]
    diff = a - b
    corr = float(np.corrcoef(a, b)[0, 1]) if np.std(a) > 1e-12 and np.std(b) > 1e-12 else None
    return {
        'mae': float(np.mean(np.abs(diff))),
        'max_abs_diff': float(np.max(np.abs(diff))),
        'corr': corr,
        'keras_abs_max': float(np.max(np.abs(a))),
        'hls_abs_max': float(np.max(np.abs(b))),
        'n_elems': int(n),
    }


def keras_trace(gap_model, x):
    import tensorflow as tf

    out = {}
    for layer in gap_model.layers:
        try:
            sub = tf.keras.Model(gap_model.input, layer.output, name='kt_' + layer.name)
        except Exception:
            continue
        out[layer.name] = sub.predict(x, verbose=0)
    return out


def hls_candidates(keras_layer, hls_keys):
    """Candidate HLS layers for a Keras layer (BN fusion variants)."""
    cands = []
    if keras_layer in hls_keys:
        cands.append(keras_layer)
    if keras_layer in FUSION_MAP and FUSION_MAP[keras_layer] in hls_keys:
        cands.append(FUSION_MAP[keras_layer])
    if keras_layer.startswith('bn_'):
        base = keras_layer[3:]  # conv1a
        if base in hls_keys:
            cands.append(base)
    if keras_layer.startswith('conv') and not keras_layer.startswith('bn'):
        bn = 'bn_' + keras_layer
        if bn in hls_keys:
            cands.append(bn)
    # unique preserve order
    seen = set()
    uniq = []
    for c in cands:
        if c not in seen:
            seen.add(c)
            uniq.append(c)
    return uniq or [keras_layer]


def load_csim_gaps(n):
    override = os.environ.get('CSIM_LOG', '').strip()
    path = Path(override) if override else HLS_PRJ / 'tb_data' / 'csim_results.log'
    if not path.is_file():
        return None
    lines = path.read_text(encoding='utf-8').strip().splitlines()
    return [[float(v) for v in ln.split()[:GAP_DIM]] for ln in lines[:n]]


def parse_defines():
    defines = HLS_PRJ / 'firmware' / 'defines.h'
    info = {}
    if not defines.is_file():
        return info
    for line in defines.read_text(encoding='utf-8').splitlines():
        if 'input_t' in line and 'typedef' in line:
            info['input_t'] = line.strip()
        if 'result_t' in line and 'typedef' in line:
            info['result_t'] = line.strip()
    return info


def main() -> int:
    if not NPZ.is_file() or not MODEL_H5.is_file():
        print('ERROR: missing npz or model', file=sys.stderr)
        return 1

    import hls4ml

    gap_model = load_gap_model()
    hls_config = build_hls_config_from_notebook()
    for lname in list(hls_config.get('LayerName', {}).keys()):
        hls_config['LayerName'][lname]['Trace'] = True

    x, labels = load_bench(N)
    x_one = x[:1]

    tmp = REPO / 'notebooks' / 'hls4ml_prj_v19_layer_align_tmp'
    print('trace convert ->', tmp)
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

    _, hls_trace_one = hls_model.trace(np.ascontiguousarray(x_one))
    hls_keys = sorted(hls_trace_one.keys()) if hls_trace_one else []
    print('hls trace layers (%d):' % len(hls_keys), hls_keys[:8], '...')

    ktrace = keras_trace(gap_model, x_one)
    csim_gaps = load_csim_gaps(N)

    # --- per-layer mapping analysis (sample 0) ---
    layer_rows = []
    best_map = {}
    for kl in KERAS_LAYER_ORDER:
        if kl not in ktrace:
            continue
        cands = hls_candidates(kl, hls_keys)
        cand_stats = []
        for hl in cands:
            if hl not in hls_trace_one:
                continue
            st = vec_stats(ktrace[kl], hls_trace_one[hl])
            if st:
                cand_stats.append({'hls_layer': hl, **st})
        cand_stats.sort(key=lambda r: r['mae'])
        default_hl = FUSION_MAP.get(kl, kl)
        default_st = next((c for c in cand_stats if c['hls_layer'] == default_hl), None)
        best = cand_stats[0] if cand_stats else None
        if best:
            best_map[kl] = best['hls_layer']
        row = {
            'keras_layer': kl,
            'default_hls': default_hl,
            'default_mae': default_st['mae'] if default_st else None,
            'best_hls': best['hls_layer'] if best else None,
            'best_mae': best['mae'] if best else None,
            'mapping_fixes_mae': (
                default_st and best and best['hls_layer'] != default_hl
                and best['mae'] < (default_st['mae'] - 1e-6)
            ),
            'candidates': cand_stats,
        }
        layer_rows.append(row)

    first_bad_fusion = next(
        (r for r in layer_rows if r['default_mae'] is not None and r['default_mae'] > MAE_THRESH),
        None,
    )
    first_bad_best = next(
        (r for r in layer_rows if r['best_mae'] is not None and r['best_mae'] > MAE_THRESH),
        None,
    )

    # --- multi-sample GAP tri-compare ---
    sys.path.insert(0, str(REPO / 'scripts'))
    os.environ.setdefault('DENSE_NPZ', str(REPO / 'deploy' / 'dense_head.npz'))
    from dma_infer_common import apply_ps_dense

    gap_rows = []
    m_kh, m_kc, m_hc = [], [], []
    top1_k = top1_h = top1_c = 0
    miscls = []

    for i in range(min(N, len(x))):
        xi = x[i:i + 1]
        kg = flatten(gap_model.predict(xi, verbose=0))[:GAP_DIM]
        hp = flatten(hls_model.predict(np.ascontiguousarray(xi)))[:GAP_DIM]
        cg = np.array(csim_gaps[i], dtype=np.float64) if csim_gaps else None

        skh = vec_stats(kg, hp)
        m_kh.append(skh['mae'])
        if cg is not None:
            skc = vec_stats(kg, cg)
            shc = vec_stats(hp, cg)
            m_kc.append(skc['mae'])
            m_hc.append(shc['mae'])
        else:
            skc = shc = None

        lab = labels[i]
        pk = int(np.argmax(apply_ps_dense(kg)))
        ph = int(np.argmax(apply_ps_dense(hp)))
        pc = int(np.argmax(apply_ps_dense(cg))) if cg is not None else None
        top1_k += int(pk == lab)
        top1_h += int(ph == lab)
        if pc is not None:
            top1_c += int(pc == lab)
        if cg is not None and pk == lab and pc != lab:
            miscls.append({
                'sample': i,
                'label': lab,
                'keras_pred': pk,
                'csim_pred': pc,
                'gap_mae_kc': skc['mae'],
                'gap_corr_kc': skc['corr'],
            })

        gap_rows.append({
            'sample': i,
            'label': lab,
            'keras_vs_hls_mae': skh['mae'],
            'keras_vs_hls_corr': skh['corr'],
            'keras_vs_csim_mae': skc['mae'] if skc else None,
            'keras_vs_csim_corr': skc['corr'] if skc else None,
            'hls_vs_csim_mae': shc['mae'] if shc else None,
            'keras_pred': pk,
            'hls_pred': ph,
            'csim_pred': pc,
            'pred_match_kc': pk == pc if pc is not None else None,
        })

    n_used = len(gap_rows)
    report = {
        'n_samples': n_used,
        'in_scale': IN_SCALE,
        'defines': parse_defines(),
        'hls_trace_layer_count': len(hls_keys),
        'hls_trace_layers': hls_keys,
        'bn_fusion_note': 'Default: Keras bn_conv* vs HLS conv* (BN fused in HLS graph)',
        'layer_mapping_analysis': layer_rows,
        'first_bad_default_fusion': first_bad_fusion,
        'first_bad_best_mapping': first_bad_best,
        'recommended_mapping': best_map,
        'gap_tri_compare': {
            'keras_vs_hls_predict_mae_mean': float(np.mean(m_kh)),
            'keras_vs_csim_mae_mean': float(np.mean(m_kc)) if m_kc else None,
            'hls_predict_vs_csim_mae_mean': float(np.mean(m_hc)) if m_hc else None,
            'top1_keras_gap_ps_pct': 100.0 * top1_k / n_used,
            'top1_hls_predict_gap_ps_pct': 100.0 * top1_h / n_used,
            'top1_csim_gap_ps_pct': 100.0 * top1_c / n_used if csim_gaps else None,
        },
        'misclassified_keras_ok_csim_bad': miscls[:10],
        'samples': gap_rows,
    }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(report, indent=2), encoding='utf-8')

    md = [
        '# v19 csim / Keras layer alignment',
        '',
        '## GAP tri-compare (%d samples)' % n_used,
        '',
        '| Path | MAE mean | Top-1 (GAP+PS) |',
        '|---|---:|---:|',
    ]
    g = report['gap_tri_compare']
    md.append('| Keras vs hls4ml predict | %.4f | %.1f%% |' % (
        g['keras_vs_hls_predict_mae_mean'], g['top1_keras_gap_ps_pct']))
    if g['keras_vs_csim_mae_mean'] is not None:
        md.append('| Keras vs csim | %.4f | %.1f%% |' % (
            g['keras_vs_csim_mae_mean'], g['top1_csim_gap_ps_pct']))
        md.append('| hls4ml predict vs csim | %.4f | — |' % g['hls_predict_vs_csim_mae_mean'])
    md.extend(['', '## Layer mapping (sample 0)', '',
               '| Keras | Default HLS | Default MAE | Best HLS | Best MAE | Fix? |',
               '|---|---|---:|---|---:|:---:|'])
    for r in layer_rows:
        fix = 'Y' if r.get('mapping_fixes_mae') else ''
        md.append('| %s | %s | %s | %s | %s | %s |' % (
            r['keras_layer'], r['default_hls'],
            '%.4f' % r['default_mae'] if r['default_mae'] is not None else '-',
            r.get('best_hls') or '-',
            '%.4f' % r['best_mae'] if r['best_mae'] is not None else '-',
            fix,
        ))
    if first_bad_fusion:
        md.append('')
        md.append('**First bad (default fusion):** `%s` MAE=%.4f' % (
            first_bad_fusion['keras_layer'], first_bad_fusion['default_mae']))
    if first_bad_best:
        md.append('**First bad (best mapping):** `%s` MAE=%.4f → `%s`' % (
            first_bad_best['keras_layer'], first_bad_best['best_mae'], first_bad_best['best_hls']))
    OUT_MD.write_text('\n'.join(md) + '\n', encoding='utf-8')

    print(json.dumps({
        'gap_tri_compare': report['gap_tri_compare'],
        'first_bad_fusion': first_bad_fusion,
        'first_bad_best': first_bad_best,
        'mapping_fixes': [r['keras_layer'] for r in layer_rows if r.get('mapping_fixes_mae')],
    }, indent=2))
    print('written:', OUT_JSON)
    print('written:', OUT_MD)
    return 0


if __name__ == '__main__':
    sys.exit(main())
