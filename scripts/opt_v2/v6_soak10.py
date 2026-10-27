#!/usr/bin/env python3
"""30 min soak at whatever clock is already loaded. Prints the raw word on the first 0xAA."""
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
    deadline = time.perf_counter() + float(os.environ.get("SOAK_S", "1800"))
    dma = DevMemDma()
    seen = 0
    checked = 0
    try:
        while time.perf_counter() < deadline:
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
            if holes or (seen % 100 == 0 and err):
                print("SOAK_BAD", seen, "idx", idx, "holes", holes, "max_lsb", err, flush=True)
                print(raw.hex(), flush=True)
                print(lsb.tolist(), flush=True)
                return 4 if holes else 5
            if seen % 100 == 0:
                checked += 1
            seen += 1
            if seen % 20000 == 0:
                print("soak", seen, "checked", checked, flush=True)
        print("SOAK_DONE", seen, checked, flush=True)
        return 0
    finally:
        dma.close()


if __name__ == "__main__":
    raise SystemExit(main())
