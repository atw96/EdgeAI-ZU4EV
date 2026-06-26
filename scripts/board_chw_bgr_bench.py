#!/usr/bin/env python3
"""On board: accuracy with CHW+BGR payload layout."""
import os
import struct
import sys

import numpy as np

from dma_infer_common import DevMemDma

CLASSES = [
    'airplane', 'automobile', 'bird', 'cat', 'deer',
    'dog', 'frog', 'horse', 'ship', 'truck',
]


def payload_chw_bgr(fixed_hwc):
    return fixed_hwc[:, :, ::-1].transpose(2, 0, 1).flatten().tobytes()


def infer_pred(dma, payload):
    dma.soft_reset()
    dma.clear_ioc()
    dma.flush_write(0x66C00000, payload)
    dma.flush_write(0x66C02000, b'\x00' * 20)
    dma.start_transfer()
    ok, _, _, _ = dma.wait_ioc()
    if not ok:
        return None
    raw = dma.inv_read(0x66C02000, 20)
    scores = [struct.unpack_from('<h', raw, k * 2)[0] / 1024.0 for k in range(10)]
    return int(np.argmax(scores))


def main():
    npz = os.environ.get('BENCH_NPZ', 'cifar10_bench.npz')
    n = int(os.environ.get('N_PROBE', '100'))
    if not os.path.isabs(npz):
        npz = os.path.join(os.path.dirname(os.path.abspath(__file__)), npz)
    data = np.load(npz, allow_pickle=True)
    labels = data['labels']
    payloads = list(data['payloads'])
    n = min(n, len(payloads))

    dma = DevMemDma()
    ok = 0
    try:
        for i in range(n):
            fixed = np.frombuffer(bytes(payloads[i]), dtype=np.int16).reshape(32, 32, 3)
            pred = infer_pred(dma, payload_chw_bgr(fixed))
            if pred is None:
                print('timeout at %d' % i)
                return 1
            if pred == int(labels[i]):
                ok += 1
        print('chw_bgr top1: %.2f%% (%d/%d)' % (100.0 * ok / n, ok, n))
    finally:
        dma.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
