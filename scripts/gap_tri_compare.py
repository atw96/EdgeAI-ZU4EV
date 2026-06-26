#!/usr/bin/env python3
"""Tri-compare: Keras GAP vs hls4ml predict vs exported AXI csim."""
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
HLS_DIR = REPO / 'notebooks' / 'hls4ml_prj'
NPZ = REPO / 'deploy' / 'cifar10_bench.npz'
N = int(__import__('os').environ.get('N_GAP_COMPARE', '10'))


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
    gap = tf.keras.Model(model.input, model.get_layer('gap').output, name='gap_only')

    cfg = hls4ml.utils.config_from_keras_model(gap, granularity='name')
    PREC_HEAD = {
        'result': 'ap_fixed<16,8>', 'accum': 'ap_fixed<16,8>',
        'weight': 'ap_fixed<16,8>', 'bias': 'ap_fixed<16,8>',
    }
    for lname in ('gap',):
        cfg['LayerName'].setdefault(lname, {})
        cfg['LayerName'][lname]['Precision'] = dict(PREC_HEAD)
    cfg['Model']['Precision'] = 'ap_fixed<16,8>'

    tmp = REPO / 'notebooks' / 'hls4ml_prj_gap_predict_tmp2'
    print('hls4ml predict tmp ->', tmp)
    hm_tmp = hls4ml.converters.convert_from_keras_model(
        gap, hls_config=cfg, output_dir=str(tmp),
        backend='Vivado', io_type='io_stream', part='xczu4ev-sfvc784-1-i', clock_period=5,
    )
    hm_tmp.compile()

    print('hls4ml predict exported dir ->', HLS_DIR)
    hm_exp = hls4ml.converters.convert_from_keras_model(
        gap, hls_config=cfg, output_dir=str(HLS_DIR),
        backend='Vivado', io_type='io_stream', part='xczu4ev-sfvc784-1-i', clock_period=5,
    )
    hm_exp.compile()

    data = np.load(NPZ, allow_pickle=True)
    csim_lines = (HLS_DIR / 'tb_data' / 'csim_results.log').read_text().strip().splitlines()
    n = min(N, len(data['payloads']), len(csim_lines))

    m_kh, m_kc, m_hc, m_ec = [], [], [], []
    for i in range(n):
        raw = bytes(data['payloads'][i])
        x = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 1024.0
        x = x.reshape(1, 32, 32, 3)
        kg = np.ravel(gap.predict(x, verbose=0))[:24]
        hp = np.ravel(hm_tmp.predict(np.ascontiguousarray(x)))[:24]
        ep = np.ravel(hm_exp.predict(np.ascontiguousarray(x)))[:24]
        cg = np.array([float(v) for v in csim_lines[i].split()[:24]])
        m_kh.append(float(np.mean(np.abs(kg - hp))))
        m_kc.append(float(np.mean(np.abs(kg - cg))))
        m_hc.append(float(np.mean(np.abs(hp - cg))))
        m_ec.append(float(np.mean(np.abs(ep - cg))))
        if i == 0:
            print('sample0 keras   ', [round(float(v), 4) for v in kg[:8]])
            print('sample0 hls tmp ', [round(float(v), 4) for v in hp[:8]])
            print('sample0 hls exp ', [round(float(v), 4) for v in ep[:8]])
            print('sample0 csim    ', [round(float(v), 4) for v in cg[:8]])

    print('MAE keras vs hls4ml tmp predict:', round(np.mean(m_kh), 4))
    print('MAE keras vs exported csim     :', round(np.mean(m_kc), 4))
    print('MAE hls4ml tmp vs exported csim:', round(np.mean(m_hc), 4))
    print('MAE hls4ml exp dir vs csim     :', round(np.mean(m_ec), 4))
    return 0


if __name__ == '__main__':
    sys.exit(main())
