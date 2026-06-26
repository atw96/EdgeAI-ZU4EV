#!/usr/bin/env python3
"""Board: raw S2MM dump + dual-scale decode + compare int16 pattern."""
import os
import struct
import sys

import numpy as np

from dma_infer_common import DevMemDma
from slot32_layout import slot32_word_map

CLASSES = [
    'airplane', 'automobile', 'bird', 'cat', 'deer',
    'dog', 'frog', 'horse', 'ship', 'truck',
]


def decode(raw, scale, layout=None, nbytes=20):
    layout = layout or os.environ.get('OUT_LAYOUT', 'int16')
    if layout == 'gap_ps':
        from dma_infer_common import apply_ps_dense
        n = int(os.environ.get('OUT_DIM', '24'))
        gap = DevMemDma.decode_slot32_raw(raw, scale, n)
        return apply_ps_dense(gap)
    if layout == 'slot32':
        n = int(os.environ.get('OUT_DIM', '10'))
        return DevMemDma.decode_slot32_raw(raw, scale, n)
    if layout == 'serial32':
        return [struct.unpack_from('<h', raw, k * 4)[0] / float(scale) for k in range(10)]
    return [struct.unpack_from('<h', raw, k * 2)[0] / float(scale) for k in range(10)]


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
        out_bytes = int(os.environ.get('OUT_BYTES', '20'))
        out_layout = os.environ.get('OUT_LAYOUT', 'int16')
        dma.flush_write(0x66C02000, b'\x00' * max(32, out_bytes))
        dma.start_transfer()
        ok, mm2s, s2mm, st = dma.wait_ioc()
        s2mm_len = dma.rd(0x80040058)
        raw = dma.inv_read(0x66C02000, max(32, out_bytes), after_dma=True)
        if out_layout in ('slot32', 'gap_ps'):
            out_dim = int(os.environ.get('OUT_DIM', '10'))
            i16 = [0] * out_dim
            for word_idx, logits in slot32_word_map(out_dim).items():
                if len(logits) == 2:
                    lo_v, hi_v = struct.unpack_from('<hh', raw, word_idx * 4)
                    i16[logits[0]], i16[logits[1]] = lo_v, hi_v
                else:
                    i16[logits[0]] = struct.unpack_from('<h', raw, word_idx * 4)[0]
        elif out_layout == 'serial32':
            i16 = [struct.unpack_from('<h', raw, k * 4)[0] for k in range(10)]
        else:
            i16 = [struct.unpack_from('<h', raw, k * 2)[0] for k in range(10)]

        print('=== board_diagnose sample0 expected=%s ===' % label)
        print('dma ok=%s status=%s mm2s=0x%08x s2mm=0x%08x' % (ok, st, mm2s, s2mm))
        print('s2mm_len_reg: %d' % s2mm_len)
        print('raw hex: %s' % raw[:out_bytes].hex())
        print('int16[0:10]: %s' % i16)
        raw_dec = raw[:out_bytes]
        print('decode /1024: %s pred=%s' % (
            [round(v, 4) for v in decode(raw_dec, 1024, out_layout)],
            CLASSES[int(np.argmax(decode(raw_dec, 1024, out_layout)))],
        ))
        print('decode /256:  %s pred=%s' % (
            [round(v, 4) for v in decode(raw_dec, 256, out_layout)],
            CLASSES[int(np.argmax(decode(raw_dec, 256, out_layout)))],
        ))
        print('mid4 int16: %s (indices 4-7)' % i16[4:8])
        print('zeros at 4-7: %s' % all(v == 0 for v in i16[4:8]))
    finally:
        dma.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
