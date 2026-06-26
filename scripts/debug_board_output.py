#!/usr/bin/env python3
"""On board: dump raw output bytes + compare npz labels with keras if model present."""
import os
import struct
import sys

import numpy as np

from dma_infer_common import DevMemDma

CLASSES = [
    'airplane', 'automobile', 'bird', 'cat', 'deer',
    'dog', 'frog', 'horse', 'ship', 'truck',
]


def infer_raw(dma, payload):
    dma.soft_reset()
    dma.clear_ioc()
    dma.flush_write(0x66C00000, payload)
    dma.flush_write(0x66C02000, b'\x00' * 20)
    dma.start_transfer()
    ok, mm2s, s2mm, status = dma.wait_ioc()
    raw = dma.inv_read(0x66C02000, 20)
    scores = [struct.unpack_from('<h', raw, k * 2)[0] / 1024.0 for k in range(10)]
    return ok, status, mm2s, s2mm, raw, scores


def main():
    npz = os.environ.get('BENCH_NPZ', 'cifar10_bench.npz')
    if not os.path.isabs(npz):
        here = os.path.dirname(os.path.abspath(__file__))
        npz = os.path.join(here, npz)
    data = np.load(npz, allow_pickle=True)
    labels = data['labels']
    payloads = list(data['payloads'])
    n = min(3, len(payloads))

    dma = DevMemDma()
    try:
        for i in range(n):
            ok, status, mm2s, s2mm, raw, scores = infer_raw(dma, payloads[i])
            pred = int(np.argmax(scores))
            print('--- sample %d expected=%s ---' % (i, CLASSES[int(labels[i])]))
            print('  dma %s mm2s=0x%08x s2mm=0x%08x' % (status, mm2s, s2mm))
            print('  raw hex: %s' % raw.hex())
            print('  int16: %s' % [struct.unpack_from('<h', raw, k * 2)[0] for k in range(10)])
            print('  scores: %s' % [round(s, 3) for s in scores])
            print('  pred: %s' % CLASSES[pred])
    finally:
        dma.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
