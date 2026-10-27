#!/usr/bin/env python3
"""Python harness x 149.9 MHz on the already-loaded bitstream.

Per frame: soft reset, clear IOC, 0xAA tail poison, 500 us poll (the
dma_infer_common default). Does not write the clock. Counts 0xAA holes
instead of stopping at the first one.
"""
import os
import time

import numpy as np

from dma_infer_common import DST_PHYS, OUT_BYTES, SRC_PHYS, DevMemDma, require_pl_operating


def as_lsb(arr):
    a = np.asarray(arr)
    if a.dtype.kind == "f":
        return np.rint(a.astype(np.float64) * 1024.0).astype(np.int32)
    return a.astype(np.int32)


def main():
    require_pl_operating()
    bench = np.load(os.environ["BENCH_NPZ"])
    golden = as_lsb(np.load(os.environ["GOLDEN_NPY"]))
    payloads = bench["payloads"]
    n10 = min(10000, len(payloads), len(golden))
    nframes = int(os.environ.get("NFRAMES", "2000000"))
    dma = DevMemDma()
    seen = 0
    holes_n = 0
    lsb_bad = 0
    max_lsb = 0
    printed = 0
    t0 = time.perf_counter()
    try:
        while seen < nframes:
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
            holes = [k for k in range(24) if raw[k * 4 + 2] == 0xAA and raw[k * 4 + 3] == 0xAA]
            gap = np.asarray(dma.decode_gap_features(raw), dtype=np.float64)
            lsb = np.rint(gap * 1024.0).astype(np.int32)
            err = int(np.abs(lsb - golden[idx]).max())
            if err > max_lsb:
                max_lsb = err
            if err:
                lsb_bad += 1
            if holes:
                holes_n += 1
                if printed < 5:
                    print("HOLE", seen, "idx", idx, "holes", holes, "max_lsb", err, flush=True)
                    print(raw.hex(), flush=True)
                    printed += 1
            seen += 1
            if seen % 20000 == 0:
                print(
                    "soak", seen, "holes", holes_n, "lsb_bad", lsb_bad,
                    "max_lsb", max_lsb, "elapsed_s", round(time.perf_counter() - t0, 1),
                    flush=True,
                )
        print(
            "SOAK_DONE", seen, "holes", holes_n, "lsb_bad", lsb_bad,
            "max_lsb", max_lsb, "elapsed_s", round(time.perf_counter() - t0, 3),
            flush=True,
        )
        return 0
    finally:
        dma.close()


if __name__ == "__main__":
    raise SystemExit(main())
