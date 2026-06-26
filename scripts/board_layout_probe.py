#!/usr/bin/env python3
"""Test hwc_flat vs chw_bgr on first 3 npz samples."""
import os
import struct
import sys

import numpy as np

from dma_infer_common import DevMemDma

CLASSES = [
    'airplane', 'automobile', 'bird', 'cat', 'deer',
    'dog', 'frog', 'horse', 'ship', 'truck',
]


def pack(name, fixed):
    if name == 'hwc_flat':
        return fixed.flatten().tobytes()
    if name == 'chw_bgr':
        return fixed[:, :, ::-1].transpose(2, 0, 1).flatten().tobytes()
    raise ValueError(name)


def infer(dma, payload):
    dma.soft_reset()
    dma.clear_ioc()
    dma.flush_write(0x66C00000, payload)
    dma.flush_write(0x66C02000, b'\x00' * 20)
    dma.start_transfer()
    ok, _, _, st = dma.wait_ioc()
    if not ok:
        return None, st
    raw = dma.inv_read(0x66C02000, 20)
    scores = [struct.unpack_from('<h', raw, k * 2)[0] / 1024.0 for k in range(10)]
    return scores, 'OK'


def main():
    npz = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cifar10_bench.npz')
    data = np.load(npz, allow_pickle=True)
    dma = DevMemDma()
    try:
        for i in range(3):
            fixed = np.frombuffer(bytes(data['payloads'][i]), dtype=np.int16).reshape(32, 32, 3)
            expect = CLASSES[int(data['labels'][i])]
            print('--- sample %d expect %s ---' % (i, expect))
            for layout in ('hwc_flat', 'chw_bgr'):
                scores, st = infer(dma, pack(layout, fixed))
                pred = CLASSES[int(np.argmax(scores))]
                print('  %s pred=%s %s scores=%s' % (
                    layout, pred, 'OK' if pred == expect else 'FAIL',
                    [round(s, 3) for s in scores],
                ))
    finally:
        dma.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
