#!/usr/bin/env python3
"""On the first 0xAA tail, re-read the same buffer without starting another DMA."""
import os
import time

import numpy as np

from dma_infer_common import DST_PHYS, OUT_BYTES, SRC_PHYS, DevMemDma, require_pl_operating


def holes_of(raw):
    return [k for k in range(24) if raw[k * 4 + 2] == 0xAA and raw[k * 4 + 3] == 0xAA]


def lsb_of(dma, raw):
    gap = np.asarray(dma.decode_gap_features(raw), dtype=np.float64)
    return np.rint(gap * 1024.0).astype(np.int32)


def main():
    require_pl_operating()
    bench = np.load(os.environ["BENCH_NPZ"])
    payloads = bench["payloads"]
    n10 = min(10000, len(payloads))
    cap = int(os.environ.get("CAP", "500000"))
    dma = DevMemDma()
    try:
        for seen in range(cap):
            idx = seen % n10
            row = payloads[idx]
            payload = row.tobytes() if isinstance(row, np.ndarray) else bytes(row)
            if not dma.soft_reset():
                print("RESET_FAIL", seen, flush=True)
                return 3
            dma.clear_ioc()
            dma.flush_write(DST_PHYS, b"\xAA" * OUT_BYTES)
            dma.flush_write(SRC_PHYS, payload)
            dma.start_transfer()
            ok, _, _, why = dma.wait_ioc()
            if not ok:
                print("FAIL", seen, why, flush=True)
                return 3
            raw = dma.inv_read(DST_PHYS, OUT_BYTES, after_dma=True)
            holes = holes_of(raw)
            if not holes:
                if seen and seen % 50000 == 0:
                    print("ok", seen, flush=True)
                continue
            print("FIRST", seen, "idx", idx, "holes", holes, flush=True)
            print("t0", raw.hex(), flush=True)
            raw2 = dma.inv_read(DST_PHYS, OUT_BYTES, after_dma=True)
            print("t_imm", holes_of(raw2), raw2.hex(), flush=True)
            time.sleep(0.001)
            raw3 = dma.inv_read(DST_PHYS, OUT_BYTES, after_dma=True)
            print("t_1ms", holes_of(raw3), raw3.hex(), flush=True)
            return 4
        print("NO_AA", cap, flush=True)
        return 0
    finally:
        dma.close()


if __name__ == "__main__":
    raise SystemExit(main())
