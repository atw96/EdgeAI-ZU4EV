#!/usr/bin/env python3
"""One protection from the C harness, added onto the Python 500 us poll path.

PROTECT=ioc   clear IOC and read it back as 0 before starting
PROTECT=len   ioc, plus reject a frame whose S2MM length is not 96
PROTECT=tail  len, plus if the last 8 bytes are still 0xAA, reread for 1 ms
"""
import os
import time

import numpy as np

from dma_infer_common import (
    DMA,
    DST_PHYS,
    ERR_MASK,
    IOC,
    MM2S_SR,
    OUT_BYTES,
    S2MM_LEN,
    S2MM_SR,
    SRC_PHYS,
    DevMemDma,
    require_pl_operating,
)


def as_lsb(arr):
    a = np.asarray(arr)
    if a.dtype.kind == "f":
        return np.rint(a.astype(np.float64) * 1024.0).astype(np.int32)
    return a.astype(np.int32)


def holes_of(raw):
    return [k for k in range(24) if raw[k * 4 + 2] == 0xAA and raw[k * 4 + 3] == 0xAA]


def ensure_idle(dma):
    for _ in range(3):
        s2 = dma.rd(DMA + S2MM_SR)
        m2 = dma.rd(DMA + MM2S_SR)
        if s2 & IOC:
            dma.wr(DMA + S2MM_SR, IOC)
        if m2 & IOC:
            dma.wr(DMA + MM2S_SR, IOC)
        s2 = dma.rd(DMA + S2MM_SR)
        m2 = dma.rd(DMA + MM2S_SR)
        if (s2 & IOC) == 0 and (m2 & IOC) == 0 and (s2 & ERR_MASK) == 0 and (m2 & ERR_MASK) == 0:
            return True
        if not dma.soft_reset():
            return False
    return False


def main():
    require_pl_operating()
    protect = os.environ.get("PROTECT", "ioc")
    if protect not in ("ioc", "len", "tail"):
        print("BAD_PROTECT", protect, flush=True)
        return 2
    bench = np.load(os.environ["BENCH_NPZ"])
    golden = as_lsb(np.load(os.environ["GOLDEN_NPY"]))
    payloads = bench["payloads"]
    n10 = min(10000, len(payloads), len(golden))
    nframes = int(os.environ.get("NFRAMES", "200000"))
    dma = DevMemDma()
    seen = 0
    holes_n = 0
    resync = 0
    idle_fail = 0
    printed = 0
    t0 = time.perf_counter()
    try:
        while seen < nframes:
            idx = seen % n10
            row = payloads[idx]
            payload = row.tobytes() if isinstance(row, np.ndarray) else bytes(row)
            if not dma.soft_reset():
                print("RESET_FAIL", protect, seen, flush=True)
                return 3
            if not ensure_idle(dma):
                idle_fail += 1
                if idle_fail > 5:
                    print("IDLE_FAIL", protect, seen, flush=True)
                    return 3
                continue
            dma.flush_write(DST_PHYS, b"\xAA" * OUT_BYTES)
            dma.flush_write(SRC_PHYS, payload)
            dma.start_transfer()
            ok, _, s2, why = dma.wait_ioc()
            if not ok:
                print("FAIL", protect, seen, why, hex(s2), flush=True)
                return 3
            if protect in ("len", "tail"):
                length = dma.rd(DMA + S2MM_LEN)
                s2 = dma.rd(DMA + S2MM_SR)
                if length != OUT_BYTES or (s2 & ERR_MASK):
                    resync += 1
                    if resync > 1000 and seen < 100:
                        print("RESYNC_RUNAWAY", protect, seen, length, hex(s2), flush=True)
                        return 4
                    continue
            raw = dma.inv_read(DST_PHYS, OUT_BYTES, after_dma=True)
            if protect == "tail" and raw[88:96] == b"\xAA" * 8:
                deadline = time.perf_counter() + 0.001
                while time.perf_counter() < deadline and raw[88:96] == b"\xAA" * 8:
                    raw = dma.inv_read(DST_PHYS, OUT_BYTES, after_dma=True)
                resync += 1
            holes = holes_of(raw)
            if holes:
                holes_n += 1
                if printed < 3:
                    print("HOLE", protect, seen, holes, flush=True)
                    printed += 1
            seen += 1
            if seen % 20000 == 0:
                print(
                    "arm", protect, seen, "holes", holes_n, "resync", resync,
                    "elapsed_s", round(time.perf_counter() - t0, 1),
                    flush=True,
                )
        print(
            "ARM_DONE", protect, seen, "holes", holes_n, "resync", resync,
            "elapsed_s", round(time.perf_counter() - t0, 3),
            flush=True,
        )
        return 0
    finally:
        dma.close()


if __name__ == "__main__":
    raise SystemExit(main())
