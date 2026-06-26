#!/usr/bin/env python3
"""Host: keras predictions for first npz samples (board payload format)."""
import os
import sys

import numpy as np

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
MODEL_H5 = os.path.join(REPO, 'notebooks', 'model_int8_qkeras.h5')
NPZ = os.path.join(REPO, 'deploy', 'cifar10_bench.npz')

CLASSES = [
    'airplane', 'automobile', 'bird', 'cat', 'deer',
    'dog', 'frog', 'horse', 'ship', 'truck',
]


def main():
    from tensorflow import keras

    try:
        from qkeras import QActivation, QConv2D, QDense, quantized_bits
        custom = {
            'QConv2D': QConv2D,
            'QDense': QDense,
            'QActivation': QActivation,
            'quantized_bits': quantized_bits,
        }
    except ImportError:
        custom = {}

    model = keras.models.load_model(MODEL_H5, custom_objects=custom, compile=False)
    data = np.load(NPZ, allow_pickle=True)
    labels = data['labels']
    payloads = list(data['payloads'])

    for i in range(min(3, len(payloads))):
        fixed = np.frombuffer(bytes(payloads[i]), dtype=np.int16).reshape(32, 32, 3)
        x = (fixed.astype(np.float32) / 1024.0).clip(0.0, 1.0)
        y = model.predict(x[np.newaxis, ...], verbose=0)[0]
        pred = int(np.argmax(y))
        print('sample %d label=%s keras_pred=%s scores=%s' % (
            i, CLASSES[int(labels[i])], CLASSES[pred],
            [round(float(v), 3) for v in y],
        ))
    return 0


if __name__ == '__main__':
    sys.exit(main())
