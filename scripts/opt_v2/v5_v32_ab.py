#!/usr/bin/env python3
"""V3.2 steps a and b on the board. One process, no retries.

Saves the bytes read back from the MM2S buffer and the raw 96-byte S2MM
buffer. History: black after reset, after a natural frame, after white,
and after black. Five repeats each.
"""
import hashlib
import os
import time

import numpy as np

from dma_infer_common import DST_PHYS, OUT_BYTES, SRC_PHYS, DevMemDma, require_pl_operating


def once(dma, payload, tag):
    dma.clear_ioc()
    dma.flush_write(DST_PHYS, b"\xAA" * OUT_BYTES)
    dma.flush_write(SRC_PHYS, payload)
    src = dma.inv_read(SRC_PHYS, len(payload), after_dma=False)
    t0 = time.perf_counter()
    dma.start_transfer()
    ok, _, _, why = dma.wait_ioc()
    dt = (time.perf_counter() - t0) * 1000.0
    if not ok:
        print("FAIL", tag, why, flush=True)
        return None
    raw = dma.inv_read(DST_PHYS, OUT_BYTES, after_dma=True)
    print("ok", tag, "ms", round(dt, 3), "src_md5", hashlib.md5(src).hexdigest(), flush=True)
    return src, raw, dt


def main():
    require_pl_operating()
    data = np.load(os.environ["BENCH_NPZ"])
    frames = {str(k): data[k].tobytes() for k in data.files}
    for need in ("black", "white", "natural", "gray51", "gray52"):
        if need not in frames:
            print("missing", need)
            return 2
    dma = DevMemDma()
    tags, srcs, raws = [], [], []

    def take(name, tag):
        got = once(dma, frames[name], tag)
        if got is None:
            return False
        src, raw, _dt = got
        tags.append(tag)
        srcs.append(np.frombuffer(src, dtype=np.uint8).copy())
        raws.append(np.frombuffer(raw, dtype=np.uint8).copy())
        return True

    try:
        if not dma.soft_reset():
            print("soft_reset failed")
            return 3
        for i in range(5):
            if not take("black", "reset_black_%d" % i):
                return 3
        for i in range(5):
            if not dma.soft_reset() or not take("natural", "pre_nat_%d" % i):
                return 3
            if not take("black", "after_nat_%d" % i):
                return 3
        for i in range(5):
            if not dma.soft_reset() or not take("white", "pre_white_%d" % i):
                return 3
            if not take("black", "after_white_%d" % i):
                return 3
        for i in range(5):
            if not dma.soft_reset() or not take("black", "pre_black_%d" % i):
                return 3
            if not take("black", "after_black_%d" % i):
                return 3
        if not dma.soft_reset() or not take("gray51", "gray51"):
            return 3
        if not dma.soft_reset() or not take("gray52", "gray52"):
            return 3
    finally:
        dma.close()
    np.savez(
        "/tmp/edgeai_bench/v32_raw.npz",
        tags=np.array(tags),
        src=np.stack(srcs),
        raw=np.stack(raws),
    )
    print("SAVED", len(tags), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
