#!/usr/bin/env python3
"""On board: one DMA transfer, print GAP features as JSON (serial/slot GAP decode)."""
import json
import os
import struct
import sys

from dma_infer_common import DevMemDma, DST_PHYS, OUT_BYTES, OUT_DIM, decode_gap_raw

OUT_SCALE = int(os.environ.get('OUT_FIXED_SCALE', '1024'))


def main():
    npz = os.environ.get('BENCH_NPZ', 'cifar10_bench.npz')
    idx = int(os.environ.get('SAMPLE_IDX', '0'))
    if not os.path.isabs(npz):
        npz = os.path.join(os.path.dirname(os.path.abspath(__file__)), npz)
    import numpy as np
    from dma_infer_common import require_pl_operating
    try:
        require_pl_operating()
    except RuntimeError as exc:
        print(json.dumps({'ok': False, 'error': str(exc)}))
        return 2

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
        gap = decode_gap_raw(raw, OUT_SCALE, OUT_DIM)
        int16_map = {
            str(idx): struct.unpack_from('<h', raw, idx * 4)[0]
            for idx in range(OUT_DIM)
        }
        out = {
            'ok': ok,
            'status': st,
            'mm2s_sr': '0x%08x' % mm2s,
            's2mm_sr': '0x%08x' % s2mm,
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