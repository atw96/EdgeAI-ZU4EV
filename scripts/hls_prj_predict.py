#!/usr/bin/env python3
"""Predict using existing hls4ml_prj (no reconvert) — same tree as bit."""
import os
import sys

import numpy as np

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
HLS_DIR = os.path.join(REPO, 'notebooks', 'hls4ml_prj')
NPZ = os.path.join(REPO, 'deploy', 'cifar10_bench.npz')
N = int(os.environ.get('N_SAMPLES', '3'))


def main():
    import yaml
    import hls4ml
    from tensorflow import keras
    from qkeras import QActivation, QConv2D, QDense, quantized_bits, quantized_relu

    custom = {
        'QConv2D': QConv2D, 'QDense': QDense, 'QActivation': QActivation,
        'quantized_bits': quantized_bits, 'quantized_relu': quantized_relu,
    }
    keras_model = keras.models.load_model(
        os.path.join(REPO, 'notebooks', 'model_int8_qkeras.h5'),
        custom_objects=custom, compile=False,
    )
    with open(os.path.join(HLS_DIR, 'hls4ml_config.yml')) as f:
        cfg = yaml.safe_load(f)['HLSConfig']

    data = np.load(NPZ, allow_pickle=True)
    classes = [
        'airplane', 'automobile', 'bird', 'cat', 'deer',
        'dog', 'frog', 'horse', 'ship', 'truck',
    ]

    hm = hls4ml.converters.convert_from_keras_model(
        keras_model, hls_config=cfg, output_dir=HLS_DIR + '_predict_tmp',
        backend='Vivado', io_type='io_stream', part='xczu4ev-sfvc784-1-i',
    )
    hm.compile()
    n = min(N, len(data['payloads']))
    print('Loaded %s' % HLS_DIR)

    for i in range(n):
        raw = bytes(data['payloads'][i])
        x = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 1024.0
        x = x.reshape(1, 32, 32, 3)
        y = np.ravel(hm.predict(np.ascontiguousarray(x)))[:10]
        print('sample %d label=%s pred=%s' % (
            i, classes[int(data['labels'][i])], classes[int(np.argmax(y))]))
        print('  raw=%s' % [round(float(v), 4) for v in y])
        print('  mid4=%s' % [round(float(v), 4) for v in y[4:8]])
    return 0


if __name__ == '__main__':
    sys.exit(main())
