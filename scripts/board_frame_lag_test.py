#!/usr/bin/env python3
"""Board test: send A,A,B,B without soft_reset to detect one-frame output lag."""
import os
import struct
import sys

import numpy as np

from dma_infer_common import DevMemDma, IN_BYTES

CLASSES = [
    'airplane', 'automobile', 'bird', 'cat', 'deer',
    'dog', 'frog', 'horse', 'ship', 'truck',
]


def load_payload(idx):
    npz = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cifar10_bench.npz')
    data = np.load(npz, allow_pickle=True)
    return bytes(data['payloads'][idx]), int(data['labels'][idx])


def infer_once(dma, payload, reset=False):
    if reset:
        dma.soft_reset()
    dma.clear_ioc()
    dma.flush_write(0x66C00000, payload)
    dma.start_transfer()
    ok, _, _, st = dma.wait_ioc()
    if not ok:
        return None, st
    raw = dma.inv_read(0x66C02000, 20, after_dma=True)
    scores = [struct.unpack_from('<h', raw, k * 2)[0] / 1024.0 for k in range(10)]
    return scores, 'OK'


def main():
    pa, la = load_payload(0)
    pb, lb = load_payload(1)
    assert len(pa) == IN_BYTES and len(pb) == IN_BYTES

    dma = DevMemDma()
    try:
        print('labels: A=%s B=%s' % (CLASSES[la], CLASSES[lb]))
        seq = [
            ('A', pa, la),
            ('A', pa, la),
            ('B', pb, lb),
            ('B', pb, lb),
        ]
        results = []
        for tag, payload, label in seq:
            scores, st = infer_once(dma, payload, reset=False)
            if scores is None:
                print('FAILED: %s' % st)
                return 1
            pred = CLASSES[int(np.argmax(scores))]
            results.append((tag, scores, pred, CLASSES[label]))
            print('%s expect=%s pred=%s scores=%s' % (
                tag, CLASSES[label], pred, [round(s, 3) for s in scores]))

        # Lag check: if output lags by 1 frame, run2≈run1 and run3≈A content
        s0, s1, s2, s3 = [r[1] for r in results]
        same01 = np.allclose(s0, s1, atol=1e-3)
        same23 = np.allclose(s2, s3, atol=1e-3)
        print('\nrun0==run1: %s  run2==run3: %s' % (same01, same23))
        if same01 and same23:
            print('HINT: stable pairs — possible pipeline warm-up or lag pattern')
    finally:
        dma.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
