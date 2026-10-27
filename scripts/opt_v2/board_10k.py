#!/usr/bin/env python3
"""10k board GAP run. On the board only, after fpga0 is operating.

Saves int16 LSB (value * 1024) so the host can rebuild exact 1/1024 floats.
RESET_EACH=1 soft-resets before every frame. A second pass with RESET_EACH=0
is started by the caller, not by this file.
"""
import os
import sys
import time

import numpy as np

from dma_infer_common import (
    DST_PHYS, OUT_BYTES, SRC_PHYS, DevMemDma, apply_ps_dense, require_pl_operating,
)


def aa_holes(raw):
    holes = []
    for k in range(24):
        if raw[k * 4 + 2] == 0xAA and raw[k * 4 + 3] == 0xAA:
            holes.append(k)
    return holes


def main():
    require_pl_operating()
    n = int(os.environ.get('N_BOARD', '10000'))
    reset_each = os.environ.get('RESET_EACH', '1') != '0'
    tag = os.environ.get('BOARD_TAG', 'reset_each')
    data = np.load(os.environ['BENCH_NPZ'], allow_pickle=True)
    n = min(n, len(data['payloads']))
    dma = DevMemDma()
    gaps = np.zeros((n, 24), dtype=np.int16)
    preds = np.zeros(n, dtype=np.int32)
    lats = np.zeros(n, dtype=np.float64)
    n_aa = 0
    done = 0
    try:
        if not reset_each:
            if not dma.soft_reset():
                print('soft_reset failed')
                return 3
        for i in range(n):
            row = data['payloads'][i]
            payload = row.tobytes() if isinstance(row, np.ndarray) else bytes(row)
            if reset_each and not dma.soft_reset():
                print('soft_reset failed', i)
                return 3
            dma.clear_ioc()
            dma.flush_write(DST_PHYS, b'\xAA' * OUT_BYTES)
            dma.flush_write(SRC_PHYS, payload)
            t0 = time.perf_counter()
            dma.start_transfer()
            ok, _, _, why = dma.wait_ioc()
            dt = (time.perf_counter() - t0) * 1000.0
            if not ok:
                print('FAIL frame', i, why)
                _save(tag, gaps, preds, lats, done)
                return 3
            raw = dma.inv_read(DST_PHYS, OUT_BYTES, after_dma=True)
            holes = aa_holes(raw)
            if holes:
                n_aa += 1
            gap = np.asarray(dma.decode_gap_features(raw), dtype=np.float64)
            lsb = np.rint(gap * 1024.0).astype(np.int16)
            gaps[i] = lsb
            scores = apply_ps_dense((lsb.astype(np.float64) / 1024.0).tolist())
            preds[i] = int(np.argmax(scores))
            lats[i] = dt
            done = i + 1
            if done % 200 == 0 or done == n:
                _save(tag, gaps, preds, lats, done)
                print('progress %d/%d median_ms %.3f aa_frames %d tag %s' % (
                    done, n, float(np.median(lats[:done])), n_aa, tag), flush=True)
    finally:
        dma.close()
    print('DONE', tag, done, 'aa_frames', n_aa)
    return 0 if n_aa == 0 else 4


def _save(tag, gaps, preds, lats, done):
    np.save('board_gap_%s.npy' % tag, gaps[:done])
    np.save('board_pred_%s.npy' % tag, preds[:done])
    np.save('board_lat_%s.npy' % tag, lats[:done])


if __name__ == '__main__':
    sys.exit(main())
