#!/usr/bin/env python3
"""Predict with exported hls4ml_prj (same tree as csynth/bit) for sample 0."""
import os
import sys

import numpy as np

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
HLS_DIR = os.path.join(REPO, 'notebooks', 'hls4ml_prj')
MODEL_H5 = os.path.join(REPO, 'notebooks', 'model_int8_qkeras.h5')
NPZ = os.path.join(REPO, 'deploy', 'cifar10_bench.npz')


def main():
    from tensorflow import keras
    import hls4ml
    from qkeras import QActivation, QConv2D, QDense, quantized_bits, quantized_relu

    custom = {
        'QConv2D': QConv2D, 'QDense': QDense, 'QActivation': QActivation,
        'quantized_bits': quantized_bits, 'quantized_relu': quantized_relu,
    }
    model = keras.models.load_model(MODEL_H5, custom_objects=custom, compile=False)
    (_, _), (x_test, y_test) = tf.keras.datasets.cifar10.load_data()
    x = x_test[:3].astype('float32') / 255.0
    y_keras = model.predict(x, verbose=0)

    config = hls4ml.utils.config_from_keras_model(model, granularity='name')
    # Mirror notebook PREC_HEAD (must match cifar10_hls4ml_synthesis.ipynb cell)
    PREC_HEAD = {
        'weight': 'ap_fixed<16,8>', 'bias': 'ap_fixed<16,8>',
        'result': 'ap_fixed<16,8>', 'accum': 'ap_fixed<16,8>',
    }
    for lname in ('gap', 'predictions'):
        config['LayerName'].setdefault(lname, {})
        config['LayerName'][lname]['Precision'] = dict(PREC_HEAD)

    hls_model = hls4ml.converters.convert_from_keras_model(
        model, hls_config=config, output_dir=HLS_DIR,
        backend='Vivado', io_type='io_stream', part='xczu4ev-sfvc784-1-i',
    )
    hls_model.compile()
    y_hls = hls_model.predict(np.ascontiguousarray(x))

    classes = [
        'airplane', 'automobile', 'bird', 'cat', 'deer',
        'dog', 'frog', 'horse', 'ship', 'truck',
    ]
    for i in range(3):
        kh = np.asarray(y_keras[i]).flatten()
        hl = np.asarray(y_hls[i]).flatten()
        print('sample %d label=%s' % (i, classes[int(y_test[i])]))
        print('  keras pred=%s' % classes[int(np.argmax(kh))])
        print('  hls   pred=%s raw=%s' % (
            classes[int(np.argmax(hl))], [round(float(v), 4) for v in hl]))
        print('  mid4=%s' % [round(float(hl[j]), 4) for j in range(4, 8)])
    return 0


if __name__ == '__main__':
    import tensorflow as tf  # noqa: F401
    sys.exit(main())
