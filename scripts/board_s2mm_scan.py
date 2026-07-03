#!/usr/bin/env python3
"""Scan S2MM buffer with variable length to locate logits 4-7."""
import os
import struct
import sys

import numpy as np

from dma_infer_common import (
    DevMemDma, DST_PHYS, DMA, IN_BYTES, OUT_BYTES,
    MM2S_CR, MM2S_SA, MM2S_SA_MSB, MM2S_LEN,
    S2MM_CR, S2MM_DA, S2MM_DA_MSB, S2MM_LEN,
)

CLASSES = [
    'airplane', 'automobile', 'bird', 'cat', 'deer',
    'dog', 'frog', 'horse', 'ship', 'truck',
]


def main():
    npz = os.environ.get('BENCH_NPZ', 'cifar10_bench.npz')
    if not os.path.isabs(npz):
        npz = os.path.join(os.path.dirname(os.path.abspath(__file__)), npz)
    out_len = int(os.environ.get('S2MM_LEN_OVERRIDE', os.environ.get('OUT_SCAN_BYTES', '64')))
    scale = int(os.environ.get('OUT_FIXED_SCALE', '256'))

    if out_len != OUT_BYTES and os.environ.get('ALLOW_PARTIAL_S2MM', '0') != '1':
        print(
            'ERROR: out_len=%d != OUT_BYTES=%d (set ALLOW_PARTIAL_S2MM=1 to override)'
            % (out_len, OUT_BYTES),
            file=sys.stderr,
        )
        return 2

    data = np.load(npz, allow_pickle=True)
    payload = bytes(data['payloads'][0])

    dma = DevMemDma()
    try:
        dma.soft_reset()
        dma.clear_ioc()
        dma.flush_write(0x66C00000, payload)
        dma.flush_write(DST_PHYS, b'\xaa' * out_len)

        # Override S2MM length for scan
        dma.wr(DMA + S2MM_DA, DST_PHYS)
        dma.wr(DMA + S2MM_DA_MSB, 0)
        dma.wr(DMA + S2MM_CR, dma.rd(DMA + S2MM_CR) | 0x1)
        dma.wr(DMA + S2MM_LEN, out_len)
        dma.wr(DMA + MM2S_SA, 0x66C00000)
        dma.wr(DMA + MM2S_SA_MSB, 0)
        dma.wr(DMA + MM2S_CR, dma.rd(DMA + MM2S_CR) | 0x1)
        dma.wr(DMA + MM2S_LEN, IN_BYTES)

        ok, _, _, st = dma.wait_ioc()
        raw = dma.inv_read(DST_PHYS, out_len, after_dma=True)

        print('=== board_s2mm_scan out_len=%d scale=%d ===' % (out_len, scale))
        print('dma ok=%s status=%s' % (ok, st))
        print('hex64: %s' % raw[:64].hex())

        for off in range(0, min(24, out_len - 19), 2):
            i16 = [struct.unpack_from('<h', raw, off + k * 2)[0] for k in range(10)]
            dec = [round(v / float(scale), 4) for v in i16]
            print('off%2d int16=%s pred=%s' % (off, i16, CLASSES[int(np.argmax(dec))]))
    finally:
        dma.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
