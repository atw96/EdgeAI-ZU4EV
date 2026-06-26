#!/usr/bin/env python3
"""
Parse HLS csynth timing/resources and run C-sim accuracy check (WSL/host).

Usage (from repo root, conda edgeai_39):
    python3 scripts/hls_metrics.py

Writes:
    results/hls_synthesis_report.json
    results/hls_csim_report.json
"""
import json
import os
import re
import sys

import numpy as np

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
HLS_RPT = os.path.join(
    REPO, 'notebooks', 'hls4ml_prj', 'myproject_prj', 'solution1',
    'syn', 'report', 'myproject_axi_csynth.rpt',
)
MODEL_H5 = os.path.join(REPO, 'notebooks', 'model_int8_qkeras.h5')
HLS_DIR = os.path.join(REPO, 'notebooks', 'hls4ml_prj')
OUT_SYNTH = os.path.join(REPO, 'results', 'hls_synthesis_report.json')
OUT_IP_LAT = os.path.join(REPO, 'results', 'hls_ip_latency.json')
OUT_CSIM = os.path.join(REPO, 'results', 'hls_csim_report.json')
N_CSIM = int(os.environ.get('N_CSIM', '100'))
SKIP_CSIM = os.environ.get('SKIP_CSIM', '0') == '1'
CLOCK_NS = 5.0


def parse_csynth_report(path):
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    text = open(path, encoding='utf-8', errors='replace').read()

    util = {}
    m = re.search(
        r'\|Total\s+\|\s+(\d+)\|\s+(\d+)\|\s+(\d+)\|\s+(\d+)\|',
        text,
    )
    if m:
        bram, dsp, ff, lut = map(int, m.groups())
        util = {
            'LUT': lut, 'FF': ff, 'DSP48E2': dsp, 'BRAM_18K': bram,
        }

    lat = {}
    m = re.search(
        r'\|\s+(\d+)\|\s+(\d+)\|\s+([\d.]+)\s*ms\s*\|\s+([\d.]+)\s*ms\s*\|\s+(\d+)\|\s+(\d+)\|',
        text,
    )
    if m:
        lat = {
            'latency_min_cycles': int(m.group(1)),
            'latency_max_cycles': int(m.group(2)),
            'latency_min_ms': float(m.group(3)),
            'latency_max_ms': float(m.group(4)),
            'ii_min_cycles': int(m.group(5)),
            'ii_max_cycles': int(m.group(6)),
        }

    return util, lat


def float_to_board_fixed(x_f32):
    """Match scripts/gen_board_samples.py / board_infer.py."""
    fixed = np.round(x_f32.astype(np.float32) * 1024.0).astype(np.int16)
    return np.clip(fixed, -32768, 32767)


def run_csim_check():
    import tensorflow as tf
    from tensorflow import keras
    import hls4ml

    if not os.path.isfile(MODEL_H5):
        raise FileNotFoundError(MODEL_H5)

    try:
        from qkeras import QActivation, QConv2D, QDense, quantized_bits, quantized_relu
        custom = {
            'QConv2D': QConv2D,
            'QDense': QDense,
            'QActivation': QActivation,
            'quantized_bits': quantized_bits,
            'quantized_relu': quantized_relu,
        }
    except ImportError:
        custom = {}

    model = keras.models.load_model(MODEL_H5, custom_objects=custom, compile=False)
    (_, _), (x_test, y_test) = tf.keras.datasets.cifar10.load_data()
    x_test = x_test.astype('float32') / 255.0
    y_true = y_test[:N_CSIM].flatten()

    X_f32 = np.ascontiguousarray(x_test[:N_CSIM])
    X_fixed = float_to_board_fixed(X_f32)

    config = hls4ml.utils.config_from_keras_model(model, granularity='name')
    hls_model = hls4ml.converters.convert_from_keras_model(
        model,
        hls_config=config,
        output_dir=HLS_DIR,
        backend='Vivado',
        io_type='io_stream',
        part='xczu4ev-sfvc784-1-i',
    )
    hls_model.compile()

    # hls4ml predict expects float [0,1]; internal quant matches training graph
    y_hls = hls_model.predict(X_f32)
    y_keras = model.predict(X_f32, verbose=0)

    classes = [
        'airplane', 'automobile', 'bird', 'cat', 'deer',
        'dog', 'frog', 'horse', 'ship', 'truck',
    ]
    print('\n--- First 3 HLS raw outputs (check class 4-7) ---')
    for i in range(min(3, len(y_hls))):
        raw = np.asarray(y_hls[i]).flatten()
        pred = int(np.argmax(raw))
        mid = [round(float(raw[j]), 4) for j in range(4, 8)]
        print(
            '  sample %d label=%s pred=%s raw=%s mid4=%s'
            % (i, classes[int(y_true[i])], classes[pred],
               [round(float(v), 4) for v in raw], mid)
        )

    hls_pred = np.argmax(y_hls, axis=1)
    keras_pred = np.argmax(y_keras, axis=1)

    # Board-format sanity: fixed-point round-trip on input only
    x_from_fixed = (X_fixed.astype(np.float32) / 1024.0).clip(0.0, 1.0)
    y_keras_fixed_in = model.predict(x_from_fixed, verbose=0)
    keras_fixed_pred = np.argmax(y_keras_fixed_in, axis=1)

    return {
        'n_samples': N_CSIM,
        'hls_vs_keras_argmax_pct': round(float(np.mean(hls_pred == keras_pred) * 100), 2),
        'hls_top1_pct': round(float(np.mean(hls_pred == y_true) * 100), 2),
        'keras_top1_pct': round(float(np.mean(keras_pred == y_true) * 100), 2),
        'keras_fixed_input_top1_pct': round(
            float(np.mean(keras_fixed_pred == y_true) * 100), 2,
        ),
        'note': (
            'hls_vs_keras should be ~100%; '
            'keras_fixed_input models board int16/1024 preprocessing'
        ),
    }


def main():
    os.chdir(REPO)
    print('Parsing %s' % HLS_RPT)
    util, lat = parse_csynth_report(HLS_RPT)

    synth = {
        'device': 'xczu4ev-sfvc784-1-i',
        'clock_mhz': 1000.0 / CLOCK_NS,
        'clock_ns': CLOCK_NS,
        'wrapped_top': 'myproject_axi',
        'resources': [
            {
                'Resource': k,
                'Used': v,
                'Available': {'LUT': 88000, 'FF': 176000, 'DSP48E2': 728, 'BRAM_18K': 252}[k],
                'Utilisation_%': round(100.0 * v / {
                    'LUT': 88000, 'FF': 176000, 'DSP48E2': 728, 'BRAM_18K': 252,
                }[k], 2),
            }
            for k, v in util.items()
        ],
        'timing': {
            'latency_min': lat.get('latency_min_cycles', 0),
            'latency_max': lat.get('latency_max_cycles', 0),
            'latency_min_ms': lat.get('latency_min_ms', 0.0),
            'latency_max_ms': lat.get('latency_max_ms', 0.0),
            'ii_min': lat.get('ii_min_cycles', 0),
            'ii_max': lat.get('ii_max_cycles', 0),
            'clock_ns': CLOCK_NS,
        },
        'throughput_fps': round(
            1000.0 / lat['latency_max_ms'], 2,
        ) if lat.get('latency_max_ms') else 0,
        'latency_ms': lat.get('latency_max_ms', 0.0),
        'source_report': HLS_RPT,
    }

    os.makedirs(os.path.dirname(OUT_SYNTH), exist_ok=True)
    with open(OUT_SYNTH, 'w', encoding='utf-8') as f:
        json.dump(synth, f, indent=2)
    print('Wrote %s' % OUT_SYNTH)

    ip_lat = {
        'metric': 'HLS IP inference latency (csynth, myproject_axi)',
        'device': synth['device'],
        'clock_mhz': synth['clock_mhz'],
        'clock_period_ns': CLOCK_NS,
        'latency_min_cycles': lat.get('latency_min_cycles', 0),
        'latency_max_cycles': lat.get('latency_max_cycles', 0),
        'latency_min_ms': lat.get('latency_min_ms', 0.0),
        'latency_max_ms': lat.get('latency_max_ms', 0.0),
        'ii_min_cycles': lat.get('ii_min_cycles', 0),
        'ii_max_cycles': lat.get('ii_max_cycles', 0),
        'pipeline_type': 'dataflow',
        'formula': 'latency_ms = latency_cycles * clock_period_ns / 1e6',
        'source_report': HLS_RPT,
        'note': 'Pure PL compute; excludes AXI-DMA and PS software overhead',
    }
    with open(OUT_IP_LAT, 'w', encoding='utf-8') as f:
        json.dump(ip_lat, f, indent=2)
    print('Wrote %s' % OUT_IP_LAT)
    print('  HLS IP latency: %.3f ms (min) / %.3f ms (max)' % (
        ip_lat['latency_min_ms'], ip_lat['latency_max_ms'],
    ))
    print('  Cycles: %d – %d @ %.0f MHz' % (
        ip_lat['latency_min_cycles'], ip_lat['latency_max_cycles'], ip_lat['clock_mhz'],
    ))

    if SKIP_CSIM:
        print('\nSKIP_CSIM=1 — accuracy check skipped')
        return 0

    print('\nRunning HLS C-sim accuracy check (%d samples)...' % N_CSIM)
    csim = run_csim_check()
    with open(OUT_CSIM, 'w', encoding='utf-8') as f:
        json.dump(csim, f, indent=2)
    print('Wrote %s' % OUT_CSIM)
    for k, v in csim.items():
        if k != 'note':
            print('  %s: %s' % (k, v))
    return 0


if __name__ == '__main__':
    sys.exit(main())
