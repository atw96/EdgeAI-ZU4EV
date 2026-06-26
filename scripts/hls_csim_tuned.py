#!/usr/bin/env python3
"""Quick hls4ml predict with raised precision on gap/predictions layers."""
import os
import sys

import numpy as np

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
MODEL_H5 = os.path.join(REPO, 'notebooks', 'model_int8_qkeras.h5')
HLS_DIR = os.path.join(REPO, 'notebooks', 'hls4ml_prj_tuned')
N_CSIM = int(os.environ.get('N_CSIM', '10'))


def main():
    import tensorflow as tf
    from tensorflow import keras
    import hls4ml
    from qkeras import QActivation, QConv2D, QDense, quantized_bits, quantized_relu

    custom = {
        'QConv2D': QConv2D, 'QDense': QDense, 'QActivation': QActivation,
        'quantized_bits': quantized_bits, 'quantized_relu': quantized_relu,
    }
    model = keras.models.load_model(MODEL_H5, custom_objects=custom, compile=False)
    (_, _), (x_test, y_test) = tf.keras.datasets.cifar10.load_data()
    x_test = x_test.astype('float32') / 255.0
    y_true = y_test[:N_CSIM].flatten()

    config = hls4ml.utils.config_from_keras_model(model, granularity='name')
    PREC_HEAD = {
        'result': 'ap_fixed<16,8>', 'accum': 'ap_fixed<16,8>',
        'weight': 'ap_fixed<16,8>', 'bias': 'ap_fixed<16,8>',
    }
    for layer in ('gap', 'predictions', 'predictions_logits'):
        config['LayerName'].setdefault(layer, {})
        config['LayerName'][layer]['Precision'] = dict(PREC_HEAD)
    config['Model']['Precision'] = 'ap_fixed<16,8>'

    # Mirror notebook: logits-only model for HLS (no softmax).
    import tensorflow as tf
    _dense_lname = None
    for _lyr in reversed(model.layers):
        if isinstance(_lyr, tf.keras.layers.Dense) or 'predictions' in _lyr.name.lower():
            _dense_lname = _lyr.name
            break
    if _dense_lname:
        _dense_lyr = model.get_layer(_dense_lname)
        _dense_w = _dense_lyr.get_weights()
        _prev_out = _dense_lyr.input
        _logits = tf.keras.layers.Dense(
            _dense_lyr.units, activation='linear',
            name=_dense_lname + '_logits',
            use_bias=len(_dense_w) == 2,
        )(_prev_out)
        model_hls = tf.keras.Model(inputs=model.input, outputs=_logits)
        model_hls.get_layer(_dense_lname + '_logits').set_weights(_dense_w)
    else:
        model_hls = model

    hls_model = hls4ml.converters.convert_from_keras_model(
        model_hls, hls_config=config, output_dir=HLS_DIR,
        backend='Vivado', io_type='io_stream', part='xczu4ev-sfvc784-1-i',
    )
    hls_model.compile()
    x_in = np.ascontiguousarray(x_test[:N_CSIM])
    y_hls = hls_model.predict(x_in)
    y_keras = model.predict(x_test[:N_CSIM], verbose=0)

    classes = [
        'airplane', 'automobile', 'bird', 'cat', 'deer',
        'dog', 'frog', 'horse', 'ship', 'truck',
    ]
    print('--- Tuned HLS first 3 outputs ---')
    for i in range(min(3, N_CSIM)):
        raw = np.asarray(y_hls[i]).flatten()
        print('  sample %d label=%s pred=%s raw=%s' % (
            i, classes[int(y_true[i])], classes[int(np.argmax(raw))],
            [round(float(v), 4) for v in raw],
        ))

    hls_top1 = float(np.mean(np.argmax(y_hls, axis=1) == y_true) * 100)
    keras_top1 = float(np.mean(np.argmax(y_keras, axis=1) == y_true) * 100)
    match = float(np.mean(np.argmax(y_hls, axis=1) == np.argmax(y_keras, axis=1)) * 100)
    print('\nTuned: hls_top1=%.1f%% keras_top1=%.1f%% hls_vs_keras=%.1f%%' % (
        hls_top1, keras_top1, match))
    return 0 if hls_top1 >= 70 else 1


if __name__ == '__main__':
    sys.exit(main())
