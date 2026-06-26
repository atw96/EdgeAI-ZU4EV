#!/usr/bin/env python3
"""On board: one DMA transfer, print GAP features as JSON (slot32 decode)."""
import json
import os
import sys

from dma_infer_common import DevMemDma, IN_BYTES, DST_PHYS, OUT_BYTES, OUT_DIM
from slot32_layout import slot32_word_map

OUT_SCALE = int(os.environ.get('OUT_FIXED_SCALE', '256'))


def main():
    npz = os.environ.get('BENCH_NPZ', 'cifar10_bench.npz')
    idx = int(os.environ.get('SAMPLE_IDX', '0'))
    if not os.path.isabs(npz):
        npz = os.path.join(os.path.dirname(os.path.abspath(__file__)), npz)
    import numpy as np
    data = np.load(npz, allow_pickle=True)
    payload = bytes(data['payloads'][idx])
    label = int(data['labels'][idx])

    dma = DevMemDma()
    try:
        dma.soft_reset()
        dma.clear_ioc()
        dma.flush_write(0x66C00000, payload)
        dma.flush_write(DST_PHYS, b'\x00' * OUT_BYTES)
        dma.start_transfer()
        ok, mm2s, s2mm, st = dma.wait_ioc()
        raw = dma.inv_read(DST_PHYS, OUT_BYTES, after_dma=True)
        gap = dma.decode_gap_features(raw, OUT_SCALE)
        int16_map = {}
        import struct
        for word_idx, logits in slot32_word_map(OUT_DIM).items():
            if len(logits) == 2:
                lo_v, hi_v = struct.unpack_from('<hh', raw, word_idx * 4)
                int16_map[str(logits[0])] = lo_v
                int16_map[str(logits[1])] = hi_v
            else:
                int16_map[str(logits[0])] = struct.unpack_from('<h', raw, word_idx * 4)[0]
        out = {
            'ok': ok,
            'status': st,
            'sample_idx': idx,
            'label': label,
            'out_bytes': OUT_BYTES,
            'out_dim': OUT_DIM,
            'out_scale': OUT_SCALE,
            'raw_hex': raw.hex(),
            'gap_float': [round(v, 6) for v in gap],
            'gap_int16': [int16_map[str(i)] for i in range(OUT_DIM)],
        }
        print(json.dumps(out))
        return 0 if ok else 1
    finally:
        dma.close()


if __name__ == '__main__':
    sys.exit(main())
