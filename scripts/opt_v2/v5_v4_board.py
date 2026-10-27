#!/usr/bin/env python3
"""V4 timing split and V5 soak on the board. One process, no retries.

Timing uses the same start_transfer -> wait_ioc window as the 10k runs.
Soak walks the packed 10k in order and checks every 100th frame against the
golden int16 GAP from today's RC1 run. A mismatch stops the loop.
"""
import glob
import os
import time

import numpy as np

from dma_infer_common import (
    DST_PHYS,
    OUT_BYTES,
    SRC_PHYS,
    DevMemDma,
    apply_ps_dense,
    require_pl_operating,
)


def aa_holes(raw):
    n = 0
    for k in range(24):
        if raw[k * 4 + 2] == 0xAA and raw[k * 4 + 3] == 0xAA:
            n += 1
    return n


def read_temp():
    vals = []
    for path in sorted(glob.glob("/sys/class/thermal/thermal_zone*/temp")):
        try:
            vals.append(int(open(path).read().strip()))
        except OSError:
            pass
    return vals


def payload_of(row):
    return row.tobytes() if isinstance(row, np.ndarray) else bytes(row)


def dma_frame(dma, payload):
    if not dma.soft_reset():
        return None
    dma.clear_ioc()
    dma.flush_write(DST_PHYS, b"\xAA" * OUT_BYTES)
    dma.flush_write(SRC_PHYS, payload)
    t0 = time.perf_counter()
    dma.start_transfer()
    ok, _, _, why = dma.wait_ioc()
    dma_ms = (time.perf_counter() - t0) * 1000.0
    if not ok:
        print("FAIL", why, flush=True)
        return None
    t1 = time.perf_counter()
    raw = dma.inv_read(DST_PHYS, OUT_BYTES, after_dma=True)
    read_ms = (time.perf_counter() - t1) * 1000.0
    gap = np.asarray(dma.decode_gap_features(raw), dtype=np.float64)
    lsb = np.rint(gap * 1024.0).astype(np.int16)
    t2 = time.perf_counter()
    apply_ps_dense((lsb.astype(np.float64) / 1024.0).tolist())
    dense_ms = (time.perf_counter() - t2) * 1000.0
    return dma_ms, read_ms, dense_ms, lsb, aa_holes(raw)


def main():
    require_pl_operating()
    data = np.load(os.environ["BENCH_NPZ"])
    golden = np.load(os.environ["GOLDEN_NPY"]).astype(np.int16)
    payloads = data["payloads"]
    n = min(len(payloads), len(golden))
    n_split = int(os.environ.get("N_SPLIT", "200"))
    n_burst = int(os.environ.get("N_BURST", "100"))
    soak_s = float(os.environ.get("SOAK_S", "1800"))
    dma = DevMemDma()
    try:
        split_dma = []
        split_read = []
        split_dense = []
        for i in range(n_split):
            got = dma_frame(dma, payload_of(payloads[i]))
            if got is None:
                return 3
            dma_ms, read_ms, dense_ms, lsb, aa = got
            if aa:
                print("AA split", i, flush=True)
                return 4
            if int(np.abs(lsb.astype(np.int32) - golden[i].astype(np.int32)).max()) != 0:
                print("SPLIT_MISMATCH", i, flush=True)
                np.save("/tmp/edgeai_bench/v4_split_bad.npy", lsb)
                return 5
            split_dma.append(dma_ms)
            split_read.append(read_ms)
            split_dense.append(dense_ms)
        # PS path only: pack, cache flush, dense. No DMA registers.
        ps = []
        dummy = (golden[0].astype(np.float64) / 1024.0).tolist()
        for i in range(n_split):
            raw_in = payload_of(payloads[i])
            t0 = time.perf_counter()
            dma.flush_write(SRC_PHYS, raw_in)
            dma.inv_read(SRC_PHYS, 64, after_dma=False)
            apply_ps_dense(dummy)
            ps.append((time.perf_counter() - t0) * 1000.0)
        burst = []
        t_prev = None
        intervals = []
        for i in range(n_burst):
            got = dma_frame(dma, payload_of(payloads[i]))
            if got is None:
                return 3
            now = time.perf_counter()
            if t_prev is not None:
                intervals.append((now - t_prev) * 1000.0)
            t_prev = now
            burst.append(got[0])
        print(
            "SPLIT dma_med %.3f read_med %.3f dense_med %.3f ps_med %.3f"
            % (
                float(np.median(split_dma)),
                float(np.median(split_read)),
                float(np.median(split_dense)),
                float(np.median(ps)),
            ),
            flush=True,
        )
        print(
            "BURST dma_med %.3f wall_interval_med %.3f n %d"
            % (float(np.median(burst)), float(np.median(intervals)), n_burst),
            flush=True,
        )
        np.savez(
            "/tmp/edgeai_bench/v4_split.npz",
            dma_ms=np.asarray(split_dma),
            read_ms=np.asarray(split_read),
            dense_ms=np.asarray(split_dense),
            ps_ms=np.asarray(ps),
            burst_dma_ms=np.asarray(burst),
            burst_interval_ms=np.asarray(intervals),
        )
        deadline = time.perf_counter() + soak_s
        seen = 0
        checked = 0
        temp0 = read_temp()
        print("SOAK start temp", temp0, "seconds", soak_s, flush=True)
        while time.perf_counter() < deadline:
            idx = seen % n
            got = dma_frame(dma, payload_of(payloads[idx]))
            if got is None:
                return 3
            _, _, _, lsb, aa = got
            if aa:
                print("AA soak", seen, idx, flush=True)
                return 4
            if seen % 100 == 0:
                delta = int(np.abs(lsb.astype(np.int32) - golden[idx].astype(np.int32)).max())
                checked += 1
                if delta != 0:
                    print("SOAK_MISMATCH", seen, idx, delta, "temp", read_temp(), flush=True)
                    np.save("/tmp/edgeai_bench/v4_soak_bad.npy", lsb)
                    return 5
            seen += 1
            if seen % 500 == 0:
                print(
                    "soak %d checked %d temp %s" % (seen, checked, read_temp()),
                    flush=True,
                )
        print(
            "SOAK_DONE frames %d checked %d temp %s" % (seen, checked, read_temp()),
            flush=True,
        )
        return 0
    finally:
        dma.close()


if __name__ == "__main__":
    raise SystemExit(main())
