#!/usr/bin/env python3
"""Quick DMA transfer diag: print channel status on success/timeout."""
import json
import os
import struct
import sys

import numpy as np

from dma_infer_common import DevMemDma, DST_PHYS, IN_BYTES, OUT_BYTES, OUT_DIM, require_pl_operating


def main():
    try:
        require_pl_operating()
    except RuntimeError as exc:
        print(json.dumps({'ok': False, 'error': str(exc)}))
        return 2

    npz = os.environ.get('BENCH_NPZ', 'cifar10_bench.npz')
    if not os.path.isabs(npz):
        npz = os.path.join(os.path.dirname(os.path.abspath(__file__)), npz)
    data = np.load(npz, allow_pickle=True)
    payload = bytes(data['payloads'][int(os.environ.get('SAMPLE_IDX', '0'))])

    dma = DevMemDma()
    try:
        snap = {}
        for name, off in (
            ('mm2s_cr', 0x00), ('mm2s_sr', 0x04),
            ('s2mm_cr', 0x30), ('s2mm_sr', 0x34),
        ):
            snap['init_' + name] = dma.rd(0x80040000 + off)

        dma.soft_reset()
        dma.clear_ioc()
        dma.flush_write(0x66C00000, payload)
        dma.flush_write(DST_PHYS, b'\x00' * OUT_BYTES)
        dma.start_transfer()

        timeout_s = float(os.environ.get('DMA_IOC_TIMEOUT_S', '8.0'))
        ok, mm2s, s2mm, st = dma.wait_ioc(timeout_s=timeout_s)
        raw = dma.inv_read(DST_PHYS, OUT_BYTES, after_dma=True)

        out = {
            'ok': ok,
            'status': st,
            'mm2s_sr': '0x%08x' % mm2s,
            's2mm_sr': '0x%08x' % s2mm,
            'mm2s_sr_end': '0x%08x' % dma.rd(0x80040004),
            's2mm_sr_end': '0x%08x' % dma.rd(0x80040034),
            'mm2s_len': dma.rd(0x80040028),
            's2mm_len': dma.rd(0x80040058),
            'raw_hex_head': raw[:32].hex(),
            'init_regs': {k: '0x%08x' % v for k, v in snap.items()},
        }
        print(json.dumps(out, indent=2))
        return 0 if ok else 1
    finally:
        dma.close()


if __name__ == '__main__':
    sys.exit(main())
