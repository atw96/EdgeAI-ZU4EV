#!/usr/bin/env python3
"""Eight-frame board smoke. Run on the board only after fpga0 is operating."""
import os
import sys
import time

import numpy as np

from dma_infer_common import DST_PHYS, OUT_BYTES, SRC_PHYS, DevMemDma, require_pl_operating

def main():
    require_pl_operating()
    os.environ.setdefault('OUT_DIM', '24')
    os.environ.setdefault('OUT_BYTES', '96')
    os.environ.setdefault('OUT_LAYOUT', 'gap_ps')
    os.environ.setdefault('OUTPUT_PACK_MODE', 'serial')
    os.environ.setdefault('OUT_FIXED_SCALE', '1024')
    data = np.load(os.environ.get('BENCH_NPZ', 'cifar10_bench.npz'), allow_pickle=True)
    payloads = list(data['payloads'])[:8]
    dma = DevMemDma()
    gaps = []
    lats = []
    aa_left = []
    try:
        for i, payload in enumerate(payloads):
            dma.soft_reset()
            dma.clear_ioc()
            dma.flush_write(DST_PHYS, b'\xAA' * OUT_BYTES)
            dma.flush_write(SRC_PHYS, payload)
            t0 = time.perf_counter()
            dma.start_transfer()
            ok, _, _, why = dma.wait_ioc()
            dt = (time.perf_counter() - t0) * 1000.0
            if not ok:
                print('FAIL frame', i, why)
                return 3
            raw = dma.inv_read(DST_PHYS, OUT_BYTES, after_dma=True)
            # serial layout stores one int16 in the low half of each 32-bit beat
            untouched = []
            for k in range(24):
                if raw[k * 4 + 2] == 0xAA and raw[k * 4 + 3] == 0xAA:
                    untouched.append(k)
            aa_left.append(untouched)
            gap = dma.decode_gap_features(raw)
            gaps.append(gap)
            lats.append(dt)
            print('frame %d %.3f ms gap0 %.6f aa_hi %s' % (i, dt, gap[0], untouched[:4]))
    finally:
        dma.close()
    np.save('smoke_gap.npy', np.asarray(gaps, dtype=np.float32))
    np.save('smoke_lat_ms.npy', np.asarray(lats, dtype=np.float64))
    print('median_ms %.4f' % float(np.median(lats)))
    print('aa_high_bytes', aa_left)
    return 0

if __name__ == '__main__':
    sys.exit(main())
