#!/usr/bin/env python3
"""Board Top-1 with vs without per-frame DMA soft_reset."""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dma_infer_common import DevMemDma, apply_ps_dense
from slot32_layout import decode_slot32_raw

NPZ = os.environ.get('BENCH_NPZ', 'cifar10_bench.npz')
N = int(os.environ.get('N_ACCURACY', '20'))
OUT_SCALE = int(os.environ.get('OUT_FIXED_SCALE', '1024'))
OUT_DIM = int(os.environ.get('OUT_DIM', '24'))
OUT_BYTES = int(os.environ.get('OUT_BYTES', '92'))


def run_loop(reset_each: bool, n: int):
    data = np.load(NPZ, allow_pickle=True)
    dma = DevMemDma()
    correct = 0
    try:
        if not reset_each:
            dma.soft_reset()
        for i in range(n):
            payload = bytes(data['payloads'][i])
            label = int(data['labels'][i])
            if reset_each:
                dma.soft_reset()
            dma.clear_ioc()
            dma.flush_write(0x66C00000, payload)
            dma.flush_write(0x66C02000, b'\x00' * OUT_BYTES)
            dma.start_transfer()
            ok, _, _, st = dma.wait_ioc()
            if not ok:
                print('fail', i, st)
                return None
            raw = dma.inv_read(0x66C02000, OUT_BYTES, after_dma=True)
            gap = decode_slot32_raw(raw, OUT_SCALE, OUT_DIM)
            pred = int(np.argmax(apply_ps_dense(gap)))
            correct += int(pred == label)
    finally:
        dma.close()
    return 100.0 * correct / n


def main():
    r1 = run_loop(True, N)
    r2 = run_loop(False, N)
    print('top1_reset_each=%.1f%% top1_no_reset=%.1f%% n=%d' % (r1, r2, N))
    return 0


if __name__ == '__main__':
    sys.exit(main())
