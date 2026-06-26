#!/usr/bin/env python3
"""hls4ml Python predict GAP + PS Dense Top-1 on bench (v19 P0-1)."""
import json
import os
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
NPZ = REPO / 'deploy' / 'cifar10_bench.npz'
DENSE_NPZ = REPO / 'deploy' / 'dense_head.npz'
OUT_JSON = REPO / 'results' / 'v19_hls4ml_predict_top1.json'
N = int(os.environ.get('N_ACCURACY', '100'))

PREC_CONV = {
    'weight': 'ap_fixed<6,1>', 'bias': 'ap_fixed<6,2>',
    'result': 'ap_fixed<6,3>', 'accum': 'ap_fixed<8,3>',
}
PREC_BN = {'scale': 'ap_fixed<8,3>', 'bias': 'ap_fixed<8,3>', 'result': 'ap_fixed<6,3>'}
PREC_ACT = {'result': 'ap_fixed<6,3>'}
PREC_GAP = {'accum': 'ap_fixed<18,10>', 'result': 'ap_fixed<16,8>'}


def main() -> int:
    import hls4ml
    import tensorflow as tf
    from qkeras import QActivation, QConv2D, QDense, quantized_bits, quantized_relu

    custom = {
        'QConv2D': QConv2D, 'QDense': QDense, 'QActivation': QActivation,
        'quantized_bits': quantized_bits, 'quantized_relu': quantized_relu,
    }
    model = tf.keras.models.load_model(
        str(REPO / 'notebooks' / 'model_int8_qkeras.h5'),
        custom_objects=custom, compile=False,
    )
    gap = tf.keras.Model(model.input, model.get_layer('gap').output, name='gap_only')

    cfg = hls4ml.utils.config_from_keras_model(gap, granularity='name')
    cfg['Model']['Precision'] = 'ap_fixed<16,8>'
    for lname in cfg['LayerName']:
        low = lname.lower()
        if 'bn_' in low:
            cfg['LayerName'][lname]['Precision'] = dict(PREC_BN)
        elif 'relu' in low or 'activation' in low:
            cfg['LayerName'][lname]['Precision'] = dict(PREC_ACT)
        elif 'conv' in low:
            cfg['LayerName'][lname]['Precision'] = dict(PREC_CONV)
        elif lname == 'gap':
            cfg['LayerName'][lname]['Precision'] = dict(PREC_GAP)

    tmp = REPO / 'notebooks' / 'hls4ml_prj_v19_predict_tmp'
    print('convert ->', tmp)
    hm = hls4ml.converters.convert_from_keras_model(
        gap, hls_config=cfg, output_dir=str(tmp),
        backend='Vivado', io_type='io_stream', part='xczu4ev-sfvc784-1-i', clock_period=5,
    )
    hm.compile()

    dh = np.load(DENSE_NPZ)
    data = np.load(NPZ, allow_pickle=True)
    n = min(N, len(data['payloads']))
    correct = 0
    maes = []
    gap_keras = tf.keras.Model(model.input, model.get_layer('gap').output)

    for i in range(n):
        raw = bytes(data['payloads'][i])
        x = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 1024.0
        x = x.reshape(1, 32, 32, 3)
        label = int(data['labels'][i])
        kg = np.ravel(gap_keras.predict(x, verbose=0))[:24]
        hp = np.ravel(hm.predict(np.ascontiguousarray(x)))[:24]
        maes.append(float(np.mean(np.abs(kg - hp))))
        logits = hp @ dh['weight'] + dh['bias']
        if int(np.argmax(logits)) == label:
            correct += 1

    report = {
        'n_samples': n,
        'hls4ml_gap_ps_dense_top1_pct': 100.0 * correct / n,
        'keras_vs_hls4ml_gap_mae_mean': float(np.mean(maes)),
        'config_source': 'v17_qat_inline',
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
