#!/usr/bin/env python3
"""Keras full-model predictions on the same 10000 packed bench images. Does not touch the h5."""
import os
from pathlib import Path

import numpy as np

os.environ.setdefault('PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION', 'python')

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / 'results' / 'opt_v2'
PACK = OUT / 'bench10k_packed.npz'


def main():
    from tensorflow import keras
    from qkeras import QActivation, QConv2D, QDense, quantized_bits, quantized_relu

    custom = {
        'QConv2D': QConv2D, 'QDense': QDense, 'QActivation': QActivation,
        'quantized_bits': quantized_bits, 'quantized_relu': quantized_relu,
    }
    model = keras.models.load_model(
        str(REPO / 'notebooks' / 'model_int8_qkeras.h5'),
        custom_objects=custom, compile=False)
    data = np.load(PACK)
    mat = data['payloads']
    y = np.asarray(data['labels'], dtype=np.int32)
    n = len(y)
    x = np.empty((n, 32, 32, 3), dtype=np.float32)
    for i in range(n):
        x[i] = np.frombuffer(mat[i].tobytes(), dtype=np.int16).astype(np.float32).reshape(32, 32, 3) / 1024.0
    prob = model.predict(x, verbose=0, batch_size=64)
    pred = np.argmax(prob, axis=1).astype(np.int32)
    gap = keras.Model(model.input, model.get_layer('gap').output).predict(x, verbose=0, batch_size=64)
    gap = np.asarray(gap, dtype=np.float32)
    np.save(OUT / 'v4_labels_10k.npy', y)
    np.save(OUT / 'v4_keras_pred_10k.npy', pred)
    np.save(OUT / 'v4_keras_gap_10k.npy', gap)
    print('keras_top1 %.4f n %d' % (100.0 * float(np.mean(pred == y)), n))


if __name__ == '__main__':
    main()
