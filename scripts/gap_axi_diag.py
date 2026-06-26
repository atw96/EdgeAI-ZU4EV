#!/usr/bin/env python3
"""Diagnose AXI csim vs hls4ml predict input/output path."""
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]


def main():
    import hls4ml
    from tensorflow import keras
    import tensorflow as tf
    from qkeras import QActivation, QConv2D, QDense, quantized_bits, quantized_relu

    custom = {
        'QConv2D': QConv2D, 'QDense': QDense, 'QActivation': QActivation,
        'quantized_bits': quantized_bits, 'quantized_relu': quantized_relu,
    }
    model = keras.models.load_model(str(REPO / 'notebooks' / 'model_int8_qkeras.h5'),
                                    custom_objects=custom, compile=False)
    gap = tf.keras.Model(model.input, model.get_layer('gap').output)
    data = np.load(REPO / 'deploy' / 'cifar10_bench.npz', allow_pickle=True)
    raw = bytes(data['payloads'][0])
    bench = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 1024.0

    (_, _), (xt, _) = tf.keras.datasets.cifar10.load_data()
    img = xt[0].astype(np.float32) / 255.0
    fixed = np.round(img * 1024).astype(np.int16)
    keras_flat = fixed.flatten().astype(np.float32) / 1024.0

    tb = [float(x) for x in (REPO / 'notebooks' / 'hls4ml_prj' / 'tb_data' /
                             'tb_input_features.dat').read_text().splitlines()[0].split()]

    print('bench vs keras flat same:', np.allclose(bench, keras_flat))
    print('bench vs keras max diff:', float(np.max(np.abs(bench - keras_flat))))
    print('tb vs bench same:', np.allclose(np.array(tb), bench))
    print('tb vs bench max diff:', float(np.max(np.abs(np.array(tb) - bench))))

    cfg = hls4ml.utils.config_from_keras_model(gap, granularity='name')
    PREC = {'result': 'ap_fixed<16,8>', 'accum': 'ap_fixed<16,8>',
            'weight': 'ap_fixed<16,8>', 'bias': 'ap_fixed<16,8>'}
    cfg['LayerName'].setdefault('gap', {})['Precision'] = dict(PREC)
    cfg['Model']['Precision'] = 'ap_fixed<16,8>'

    # predict with HWC numpy (what works)
    x_hwc = bench.reshape(1, 32, 32, 3)
    y_hwc = np.ravel(gap.predict(x_hwc, verbose=0))[:24]

    # predict with flat array if API allows
    tmp = str(REPO / 'notebooks' / 'hls4ml_prj_gap_predict_tmp3')
    hm = hls4ml.converters.convert_from_keras_model(
        gap, hls_config=cfg, output_dir=tmp,
        backend='Vivado', io_type='io_stream', part='xczu4ev-sfvc784-1-i', clock_period=5,
    )
    hm.compile()
    y_hls = np.ravel(hm.predict(np.ascontiguousarray(x_hwc)))[:24]

    # try flat 1x3072 reshape variants
    flat = bench
    variants = {
        'hwc_flat': flat.reshape(1, 32, 32, 3),
        'chw_flat': flat.reshape(3, 32, 32).transpose(1, 2, 0).reshape(1, 32, 32, 3),
    }
    for name, arr in variants.items():
        y = np.ravel(hm.predict(np.ascontiguousarray(arr)))[:24]
        mae = float(np.mean(np.abs(y_hls - y)))
        print('%s vs default mae' % name, mae)

    csim = [float(v) for v in (REPO / 'notebooks' / 'hls4ml_prj' / 'tb_data' /
                               'csim_results.log').read_text().splitlines()[0].split()]
    print('keras gap[:8]', [round(v, 4) for v in y_hwc[:8]])
    print('hls predict[:8]', [round(v, 4) for v in y_hls[:8]])
    print('csim axi[:8]', [round(v, 4) for v in csim[:8]])
    print('mae keras-hls', float(np.mean(np.abs(y_hwc - y_hls))))
    print('mae hls-csim', float(np.mean(np.abs(y_hls - np.array(csim[:24])))))
    return 0


if __name__ == '__main__':
    sys.exit(main())
