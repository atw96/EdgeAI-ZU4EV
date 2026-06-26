#!/usr/bin/env python3
"""
Compare GAP 24-dim: HLS csim (hls4ml predict) vs Keras gap vs board DMA decode.
Checks ap_fixed<16,8> scale alignment (256 vs 1024).
"""
import json
import os
import re
import struct
import subprocess
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
HLS_DIR = REPO / 'notebooks' / 'hls4ml_prj'
MODEL_H5 = REPO / 'notebooks' / 'model_int8_qkeras.h5'
NPZ = REPO / 'deploy' / 'cifar10_bench.npz'
META = HLS_DIR / 'axi_wrapper_meta.json'
OUT_JSON = REPO / 'results' / 'gap_csim_board_compare.json'

N_SAMPLES = int(os.environ.get('N_GAP_COMPARE', '10'))
BOARD_IP = os.environ.get('BOARD_IP', '192.168.1.40')
BOARD_PASS = os.environ.get('BOARD_PASS', 'root')
GAP_DIM = 24


def load_scales():
    if META.is_file():
        meta = json.loads(META.read_text(encoding='utf-8'))
        return meta.get('input_scale', 1024), meta.get('output_scale', 256)
    defines = (HLS_DIR / 'firmware' / 'defines.h').read_text(encoding='utf-8')
    m_in = re.search(r'typedef nnet::array<ap_fixed<(\d+),(\d+)>, 3\*1> input_t', defines)
    m_out = re.search(r'typedef nnet::array<ap_fixed<(\d+),(\d+)>, 24\*1> result_t', defines)
    in_scale = 1 << (int(m_in.group(1)) - int(m_in.group(2))) if m_in else 1024
    out_scale = 1 << (int(m_out.group(1)) - int(m_out.group(2))) if m_out else 256
    return in_scale, out_scale


def payload_to_input(raw, in_scale):
    x = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / float(in_scale)
    return x.reshape(1, 32, 32, 3)


def float_to_ap_fixed_int16(values, scale):
    return [int(np.clip(round(float(v) * scale), -32768, 32767)) for v in values]


def load_keras_gap():
    from tensorflow import keras
    from qkeras import QActivation, QConv2D, QDense, quantized_bits, quantized_relu

    custom = {
        'QConv2D': QConv2D, 'QDense': QDense, 'QActivation': QActivation,
        'quantized_bits': quantized_bits, 'quantized_relu': quantized_relu,
    }
    model = keras.models.load_model(str(MODEL_H5), custom_objects=custom, compile=False)
    import tensorflow as tf
    gap_model = tf.keras.Model(model.input, model.get_layer('gap').output, name='gap_only')
    return model, gap_model


def load_hls_model(gap_keras_model):
    """hls4ml 0.8.x predict on exported hls4ml_prj (GAP-only, same tree as bit)."""
    import hls4ml

    cfg = hls4ml.utils.config_from_keras_model(gap_keras_model, granularity='name')
    PREC_HEAD = {
        'result': 'ap_fixed<16,8>', 'accum': 'ap_fixed<16,8>',
        'weight': 'ap_fixed<16,8>', 'bias': 'ap_fixed<16,8>',
    }
    for lname in ('gap',):
        cfg['LayerName'].setdefault(lname, {})
        cfg['LayerName'][lname]['Precision'] = dict(PREC_HEAD)
    cfg['Model']['Precision'] = 'ap_fixed<16,8>'

    predict_dir = REPO / 'notebooks' / 'hls4ml_prj_gap_predict_tmp'
    print('HLS csim: hls4ml predict (tmp=%s, compile may take minutes)...' % predict_dir)
    hm = hls4ml.converters.convert_from_keras_model(
        gap_keras_model,
        hls_config=cfg,
        output_dir=str(predict_dir),
        backend='Vivado',
        io_type='io_stream',
        part='xczu4ev-sfvc784-1-i',
        clock_period=5,
    )
    hm.compile()
    return hm


def fetch_board_sample(idx, out_scale):
    env = (
        'OUT_DIM=24 OUT_BYTES=92 OUT_LAYOUT=gap_ps OUT_FIXED_SCALE=%d SAMPLE_IDX=%d'
    ) % (out_scale, idx)
    cmd = [
        'sshpass', '-p', BOARD_PASS,
        'ssh', '-o', 'StrictHostKeyChecking=no',
        'root@%s' % BOARD_IP,
        'cd /tmp/edgeai_bench && %s python3 -u board_fetch_gap.py' % env,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if proc.returncode != 0:
        raise RuntimeError('board_fetch failed: %s' % proc.stderr[-500:])
    line = proc.stdout.strip().splitlines()[-1]
    return json.loads(line)


def compare_vectors(name_a, a, name_b, b):
    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    diff = a - b
    return {
        'pair': '%s vs %s' % (name_a, name_b),
        'mae': float(np.mean(np.abs(diff))),
        'max_abs': float(np.max(np.abs(diff))),
        'corr': float(np.corrcoef(a, b)[0, 1]) if np.std(a) > 0 and np.std(b) > 0 else None,
        'match_int16': float(np.mean(
            float_to_ap_fixed_int16(a, 256) == float_to_ap_fixed_int16(b, 256)
        ) * 100),
    }


def main():
    if not NPZ.is_file():
        print('ERROR: missing %s' % NPZ, file=sys.stderr)
        return 1
    if not HLS_DIR.is_dir():
        print('ERROR: missing HLS project %s' % HLS_DIR, file=sys.stderr)
        return 1

    in_scale, out_scale = load_scales()
    print('input_scale=%d output_scale=%d (ap_fixed<16,8>)' % (in_scale, out_scale))

    data = np.load(NPZ, allow_pickle=True)
    n = min(N_SAMPLES, len(data['payloads']))
    classes = [
        'airplane', 'automobile', 'bird', 'cat', 'deer',
        'dog', 'frog', 'horse', 'ship', 'truck',
    ]

    _, gap_keras = load_keras_gap()
    hm = load_hls_model(gap_keras)

    samples = []
    summary = {
        'hls_vs_keras': [],
        'board_vs_hls': [],
        'board_vs_keras': [],
        'board_scale256_vs_1024': [],
    }

    for i in range(n):
        raw = bytes(data['payloads'][i])
        x = payload_to_input(raw, in_scale)
        hls_gap = np.ravel(hm.predict(np.ascontiguousarray(x)))[:GAP_DIM]
        keras_gap = np.ravel(gap_keras.predict(x, verbose=0))[:GAP_DIM]
        hls_i16 = float_to_ap_fixed_int16(hls_gap, out_scale)

        board = fetch_board_sample(i, out_scale)
        board_gap256 = board['gap_float']
        board_i16 = board['gap_int16']
        board_gap1024 = [v / 1024.0 for v in board_i16]

        i16_match = float(np.mean(np.asarray(board_i16) == np.asarray(hls_i16)) * 100)
        rec = {
            'sample': i,
            'label': classes[int(data['labels'][i])],
            'keras_gap': [round(float(v), 6) for v in keras_gap],
            'hls_gap': [round(float(v), 6) for v in hls_gap],
            'hls_int16': hls_i16,
            'board_gap_div256': board_gap256,
            'board_gap_div1024': [round(v, 6) for v in board_gap1024],
            'board_int16': board_i16,
            'board_raw_hex': board['raw_hex'],
            'board_i16_match_hls_pct': i16_match,
            'cmp': {
                'hls_vs_keras': compare_vectors('hls', hls_gap, 'keras', keras_gap),
                'board256_vs_hls': compare_vectors('board/256', board_gap256, 'hls', hls_gap),
                'board256_vs_keras': compare_vectors('board/256', board_gap256, 'keras', keras_gap),
                'board1024_vs_hls': compare_vectors('board/1024', board_gap1024, 'hls', hls_gap),
            },
        }
        samples.append(rec)
        for k in summary:
            key = k.replace('hls_vs_keras', 'hls_vs_keras').replace('board_vs_hls', 'board256_vs_hls')
            if k == 'hls_vs_keras':
                summary[k].append(rec['cmp']['hls_vs_keras']['mae'])
            elif k == 'board_vs_hls':
                summary[k].append(rec['cmp']['board256_vs_hls']['mae'])
            elif k == 'board_vs_keras':
                summary[k].append(rec['cmp']['board256_vs_keras']['mae'])
            elif k == 'board_scale256_vs_1024':
                summary[k].append(rec['cmp']['board1024_vs_hls']['mae'])

    def agg(vals):
        return {'mean_mae': float(np.mean(vals)), 'max_mae': float(np.max(vals))}

    report = {
        'n_samples': n,
        'in_scale': in_scale,
        'out_scale': out_scale,
        'result_type': 'ap_fixed<16,8>',
        'summary_mae': {
            'hls_vs_keras': agg(summary['hls_vs_keras']),
            'board_div256_vs_hls': agg(summary['board_vs_hls']),
            'board_div256_vs_keras': agg(summary['board_vs_keras']),
            'board_div1024_vs_hls': agg(summary['board_scale256_vs_1024']),
        },
        'scale_verdict': None,
        'samples': samples,
    }

    mae256 = report['summary_mae']['board_div256_vs_hls']['mean_mae']
    mae1024 = report['summary_mae']['board_div1024_vs_hls']['mean_mae']
    if mae1024 < mae256 * 0.5:
        report['scale_verdict'] = 'board likely needs OUT_FIXED_SCALE=1024 not 256'
    elif mae256 < 0.05:
        report['scale_verdict'] = 'board aligned with HLS at scale 256'
    elif mae256 < mae1024:
        report['scale_verdict'] = 'scale 256 closer than 1024 but still large error — PL/bit mismatch'
    else:
        report['scale_verdict'] = 'board GAP diverges from HLS csim — check bit/IP or DMA decode'

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report['summary_mae'], indent=2))
    print('scale_verdict:', report['scale_verdict'])
    print('written:', OUT_JSON)
    return 0


if __name__ == '__main__':
    sys.exit(main())
