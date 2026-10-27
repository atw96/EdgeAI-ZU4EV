#!/usr/bin/env python3
"""Four extreme frames: black, white, checker, single-channel saturation.

Writes a packed npz the board script can run, plus Keras GAP for the 1-LSB check.
"""
import os
from pathlib import Path

import numpy as np

os.environ.setdefault('PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION', 'python')
REPO = Path(__file__).resolve().parents[2]
OUT = REPO / 'results' / 'opt_v2'


def img_to_payload(img_uint8):
    fixed = np.round(img_uint8.astype(np.float32) / 255.0 * 1024.0).astype(np.int16)
    return np.frombuffer(fixed.tobytes(), dtype=np.uint8).copy()


def main():
    black = np.zeros((32, 32, 3), dtype=np.uint8)
    white = np.full((32, 32, 3), 255, dtype=np.uint8)
    checker = np.zeros((32, 32, 3), dtype=np.uint8)
    checker[0::2, 0::2] = 255
    checker[1::2, 1::2] = 255
    sat = np.zeros((32, 32, 3), dtype=np.uint8)
    sat[:, :, 0] = 255
    images = [black, white, checker, sat]
    mat = np.stack([img_to_payload(im) for im in images])
    labels = np.zeros(4, dtype=np.int32)
    np.savez(OUT / 'bench_extreme.npz', payloads=mat, labels=labels)

    from tensorflow import keras
    from qkeras import QActivation, QConv2D, QDense, quantized_bits, quantized_relu
    custom = {
        'QConv2D': QConv2D, 'QDense': QDense, 'QActivation': QActivation,
        'quantized_bits': quantized_bits, 'quantized_relu': quantized_relu,
    }
    model = keras.models.load_model(
        str(REPO / 'notebooks' / 'model_int8_qkeras.h5'),
        custom_objects=custom, compile=False)
    x = np.stack([im.astype(np.float32) / 255.0 for im in images])
    gap = keras.Model(model.input, model.get_layer('gap').output).predict(x, verbose=0)
    np.save(OUT / 'v4_keras_gap_extreme.npy', np.asarray(gap, dtype=np.float32))
    print('extreme keras gap', np.round(np.asarray(gap)[:, :4], 4).tolist())


if __name__ == '__main__':
    main()
