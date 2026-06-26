#!/usr/bin/env python3
"""Compare hls4ml predict (notebook config) vs board int16 decode for demo samples."""
import json
import os
import re
import struct
import sys

import numpy as np

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
HLS_DIR = os.path.join(REPO, 'notebooks', 'hls4ml_prj')
MODEL_H5 = os.path.join(REPO, 'notebooks', 'model_int8_qkeras.h5')
NPZ = os.path.join(REPO, 'deploy', 'cifar10_bench.npz')
META = os.path.join(HLS_DIR, 'axi_wrapper_meta.json')


def load_output_scale():
    if os.path.isfile(META):
        return json.load(open(META))['output_scale']
    defines = open(os.path.join(HLS_DIR, 'firmware', 'defines.h')).read()
    m = re.search(r'typedef nnet::array<ap_fixed<(\d+),(\d+)>, 10\*1> result_t', defines)
    w, i = int(m.group(1)), int(m.group(2))
    return 1 << (w - i)


def build_hls_config(model):
    import hls4ml
    cfg = hls4ml.utils.config_from_keras_model(model, granularity='name')
    cfg['Model']['Precision'] = 'ap_fixed<16,8>'
    head = {
        'result': 'ap_fixed<16,8>', 'accum': 'ap_fixed<16,8>',
        'weight': 'ap_fixed<16,8>', 'bias': 'ap_fixed<16,8>',
    }
    for ln in ('gap', 'predictions', 'predictions_logits'):
        cfg['LayerName'].setdefault(ln, {})
        cfg['LayerName'][ln]['Precision'] = dict(head)
    return cfg


def logits_model(model):
    import tensorflow as tf
    for lyr in reversed(model.layers):
        if isinstance(lyr, tf.keras.layers.Dense) or 'predictions' in lyr.name.lower():
            d = model.get_layer(lyr.name)
            w = d.get_weights()
            prev = d.input
            logits = tf.keras.layers.Dense(
                d.units, activation='linear', name=lyr.name + '_logits',
                use_bias=len(w) == 2,
            )(prev)
            mh = tf.keras.Model(model.input, logits)
            mh.get_layer(lyr.name + '_logits').set_weights(w)
            return mh
    return model


def decode_board_raw(raw20, out_scale=256):
    return [struct.unpack_from('<h', raw20, k * 2)[0] / float(out_scale) for k in range(10)]


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
    mh = logits_model(model)
    cfg = build_hls_config(model)

    # Do NOT reconvert — that overwrites hls4ml_prj and can break csynth RF/partition limits.
    import hls4ml.model
    hls4ml_cfg = os.path.join(HLS_DIR, 'hls4ml_config.yml')
    if not os.path.isfile(hls4ml_cfg):
        print('WARN: missing %s — skip predict validation' % hls4ml_cfg)
        return 0
    hm = hls4ml.model.load_model(HLS_DIR)

    data = np.load(NPZ, allow_pickle=True)
    n = min(3, len(data['payloads']))
    out_scale = load_output_scale()
    classes = [
        'airplane', 'automobile', 'bird', 'cat', 'deer',
        'dog', 'frog', 'horse', 'ship', 'truck',
    ]

    print('output_scale=%d (ap_fixed decode divisor)' % out_scale)
    for i in range(n):
        raw = bytes(data['payloads'][i])
        x = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 1024.0
        x = x.reshape(32, 32, 3)
        y = hm.predict(np.ascontiguousarray(x[np.newaxis, ...]))
        hls = np.ravel(y)[:10]
        if len(hls) < 10:
            print('WARN: expected 10 logits, got shape %s' % (np.asarray(y).shape,))
            continue
        # simulate AXI pack/unpack: float -> ap_fixed<16,8> bits -> board decode
        sim_raw = b''.join(
            struct.pack('<h', int(np.clip(round(float(v) * out_scale), -32768, 32767)))
            for v in hls
        )
        sim_dec = decode_board_raw(sim_raw, out_scale)

        print('\nsample %d label=%s' % (i, classes[int(data['labels'][i])]))
        print('  hls predict   : %s' % [round(float(v), 4) for v in hls])
        print('  hls mid4      : %s pred=%s' % (
            [round(float(v), 4) for v in hls[4:8]], classes[int(np.argmax(hls))]))
        print('  sim pack/unpack (scale %d): %s' % (
            out_scale, [round(v, 4) for v in sim_dec]))
    return 0


if __name__ == '__main__':
    sys.exit(main())
