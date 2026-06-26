#!/usr/bin/env python3
import os
import struct
import sys

import numpy as np

from dma_infer_common import DevMemDma

def main():
    npz = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cifar10_bench.npz')
    data = np.load(npz, allow_pickle=True)
    payload = bytes(data['payloads'][0])

    dma = DevMemDma()
    try:
        dma.soft_reset()
        dma.clear_ioc()
        dma.flush_write(0x66C00000, payload)
        dma.start_transfer()
        ok, _, _, st = dma.wait_ioc()
        raw = dma.inv_read(0x66C02000, 64, after_dma=True)
        print('dma', st, 'hex64', raw.hex())
        for off in range(0, 24, 2):
            vals = [struct.unpack_from('<h', raw, off + k * 2)[0] for k in range(10)]
            print('off %2d int16=%s' % (off, vals))
    finally:
        dma.close()
    return 0

if __name__ == '__main__':
    sys.exit(main())
