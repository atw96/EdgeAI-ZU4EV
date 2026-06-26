#!/usr/bin/env python3
"""Strategy step ②: prefill S2MM buffer with 0xAA, distinguish RTL-zero vs beat-loss."""
import os
import struct
import sys

import numpy as np

from dma_infer_common import DevMemDma, DST_PHYS

CLASSES = [
    'airplane', 'automobile', 'bird', 'cat', 'deer',
    'dog', 'frog', 'horse', 'ship', 'truck',
]


def main():
    npz = os.environ.get('BENCH_NPZ', 'cifar10_bench.npz')
    if not os.path.isabs(npz):
        npz = os.path.join(os.path.dirname(os.path.abspath(__file__)), npz)
    data = np.load(npz, allow_pickle=True)
    payload = bytes(data['payloads'][0])
    label = CLASSES[int(data['labels'][0])]

    dma = DevMemDma()
    try:
        dma.soft_reset()
        dma.clear_ioc()
        dma.flush_write(0x66C00000, payload)
        # Prefill output buffer with 0xAA pattern (32 bytes)
        dma.flush_write(DST_PHYS, b'\xaa' * 32)

        dma.start_transfer()
        ok, mm2s, s2mm, st = dma.wait_ioc()
        raw = dma.inv_read(DST_PHYS, 32, after_dma=True)
        i16 = [struct.unpack_from('<h', raw, k * 2)[0] for k in range(10)]
        b = list(raw[:20])

        print('=== board_aa_prefill_test expected=%s ===' % label)
        print('dma ok=%s status=%s' % (ok, st))
        print('raw20 hex: %s' % raw[:20].hex())
        print('bytes[8:16] (idx4-7): %s' % [hex(x) for x in b[8:16]])
        print('int16[4:8]: %s' % i16[4:8])

        mid_bytes = b[8:16]
        if all(x == 0xAA for x in mid_bytes):
            print('VERDICT: beat_not_written — DMA/converter did not overwrite bytes 8-15')
        elif all(x == 0 for x in mid_bytes):
            print('VERDICT: PL_wrote_zero — RTL wrote 0 for class 4-7')
        elif all(x == 0 for x in i16[4:8]):
            print('VERDICT: mixed_pattern — bytes changed but int16 mid4 is zero')
        else:
            print('VERDICT: mid4_nonzero — logits 4-7 present in buffer')
    finally:
        dma.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
