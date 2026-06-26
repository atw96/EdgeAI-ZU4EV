#!/usr/bin/env python3
import os
import sys

import numpy as np

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
MODEL = os.path.join(REPO, 'deploy', 'model_int8.tflite')
NPZ = os.path.join(REPO, 'deploy', 'cifar10_bench.npz')
CLASSES = [
    'airplane', 'automobile', 'bird', 'cat', 'deer',
    'dog', 'frog', 'horse', 'ship', 'truck',
]


def main():
    import tensorflow as tf

    interp = tf.lite.Interpreter(model_path=MODEL)
    interp.allocate_tensors()
    in_d = interp.get_input_details()[0]
    out_d = interp.get_output_details()[0]
    data = np.load(NPZ, allow_pickle=True)

    for i in range(3):
        fixed = np.frombuffer(bytes(data['payloads'][i]), dtype=np.int16).reshape(32, 32, 3)
        x = (fixed.astype(np.float32) / 1024.0).clip(0.0, 1.0)
        if in_d['dtype'] == np.int8:
            sc, zp = in_d['quantization']
            inp = ((x / sc) + zp).astype(np.int8)
        else:
            inp = x.astype(np.float32)
        interp.set_tensor(in_d['index'], inp[np.newaxis, ...])
        interp.invoke()
        raw = interp.get_tensor(out_d['index'])[0]
        if out_d['dtype'] == np.int8:
            sc, zp = out_d['quantization']
            raw = (raw.astype(np.float32) - zp) * sc
        pred = int(np.argmax(raw))
        print(
            'sample %d label=%s pred=%s scores=%s'
            % (i, CLASSES[int(data['labels'][i])], CLASSES[pred], list(np.round(raw, 3)))
        )
    return 0


if __name__ == '__main__':
    sys.exit(main())
