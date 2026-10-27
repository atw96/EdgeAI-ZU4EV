#!/usr/bin/env python3
"""S1 clock ladder and S2 per-stage timing. Restores PL0 divisor 15 on exit.

DMA must already be idle when the divisor changes. PL must be operating.
"""
import os
import struct
import time

import mmap
import numpy as np

from dma_infer_common import (
    DST_PHYS,
    OUT_BYTES,
    SRC_PHYS,
    DevMemDma,
    apply_ps_dense,
    require_pl_operating,
)

PARENT_HZ = 1499135828.0
PL0_PAGE = 0xFF5E0000
PL0_OFF = 0xC0
DIV1_MASK = 0x3F00


def as_lsb(arr):
    a = np.asarray(arr)
    if a.dtype.kind == "f":
        return np.rint(a.astype(np.float64) * 1024.0).astype(np.int32)
    return a.astype(np.int32)


def payload_of(row):
    return row.tobytes() if isinstance(row, np.ndarray) else bytes(row)


def aa_count(raw):
    n = 0
    for k in range(24):
        if raw[k * 4 + 2] == 0xAA and raw[k * 4 + 3] == 0xAA:
            n += 1
    return n


class Pl0:
    def __init__(self):
        self.fd = os.open("/dev/mem", os.O_RDWR | os.O_SYNC)
        self.mm = mmap.mmap(
            self.fd, 0x1000, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE, offset=PL0_PAGE
        )

    def close(self):
        self.mm.close()
        os.close(self.fd)

    def read(self):
        return struct.unpack_from("<I", self.mm, PL0_OFF)[0]

    def mhz(self, val):
        div0 = (val >> 16) & 0x3F
        div1 = (val >> 8) & 0x3F
        if div0 == 0 or div1 == 0:
            return 0.0
        return PARENT_HZ / (div0 * div1) / 1e6

    def set_div1(self, div1):
        cur = self.read()
        val = (cur & ~DIV1_MASK) | ((int(div1) & 0x3F) << 8)
        struct.pack_into("<I", self.mm, PL0_OFF, val)
        time.sleep(0.01)
        got = self.read()
        back = (got >> 8) & 0x3F
        if back != div1:
            raise RuntimeError("div1 readback %s wanted %s reg 0x%08x" % (back, div1, got))
        return self.mhz(got), got


def one_frame(dma, payload, do_reset):
    t_reset = 0.0
    t0 = time.perf_counter()
    if do_reset and not dma.soft_reset():
        return None
    if do_reset:
        t_reset = (time.perf_counter() - t0) * 1000.0
    dma.clear_ioc()
    t1 = time.perf_counter()
    dma.flush_write(DST_PHYS, b"\xAA" * OUT_BYTES)
    dma.flush_write(SRC_PHYS, payload)
    t_flush = (time.perf_counter() - t1) * 1000.0
    t2 = time.perf_counter()
    dma.start_transfer()
    ok, _, _, why = dma.wait_ioc()
    t_window = (time.perf_counter() - t2) * 1000.0
    if not ok:
        print("FAIL", why, flush=True)
        return None
    t3 = time.perf_counter()
    raw = dma.inv_read(DST_PHYS, OUT_BYTES, after_dma=True)
    t_read = (time.perf_counter() - t3) * 1000.0
    gap = np.asarray(dma.decode_gap_features(raw), dtype=np.float64)
    lsb = np.rint(gap * 1024.0).astype(np.int32)
    t4 = time.perf_counter()
    apply_ps_dense((lsb.astype(np.float64) / 1024.0).tolist())
    t_dense = (time.perf_counter() - t4) * 1000.0
    return t_reset, t_flush, t_window, t_read, t_dense, lsb, aa_count(raw)


def run_set(dma, payloads, golden, n, do_reset):
    windows = []
    max_lsb = 0
    for i in range(n):
        got = one_frame(dma, payload_of(payloads[i]), do_reset)
        if got is None:
            return None
        _, _, window, _, _, lsb, aa = got
        if aa:
            print("AA", i, flush=True)
            return None
        err = int(np.abs(lsb - golden[i]).max())
        if err > max_lsb:
            max_lsb = err
        windows.append(window)
        if max_lsb:
            print("MISMATCH", i, max_lsb, flush=True)
            return None
    return np.asarray(windows), max_lsb


def main():
    require_pl_operating()
    bench = np.load(os.environ["BENCH_NPZ"])
    golden = as_lsb(np.load(os.environ["GOLDEN_NPY"]))
    kat = np.load(os.environ["KAT_NPZ"])
    kat_g = as_lsb(np.load(os.environ["KAT_GOLDEN"])["gap"])
    payloads = bench["payloads"]
    n1000 = min(1000, len(payloads), len(golden))
    dma = DevMemDma()
    clk = Pl0()
    lines = ["f_mhz,window_ms,p99_ms,max_lsb,div1"]
    try:
        rows = []
        for i in range(200):
            got = one_frame(dma, payload_of(payloads[i]), True)
            if got is None:
                return 3
            rows.append(got[:5])
        arr = np.asarray(rows, dtype=np.float64)
        names = ("reset", "flush", "window", "read", "dense")
        print("SPLIT_RESET", " ".join("%s %.3f" % (names[k], float(np.median(arr[:, k]))) for k in range(5)), flush=True)
        nore = []
        t_prev = None
        intervals = []
        for i in range(100):
            t_call = time.perf_counter()
            got = one_frame(dma, payload_of(payloads[i]), False)
            if got is None:
                return 3
            if t_prev is not None:
                intervals.append((t_call - t_prev) * 1000.0)
            t_prev = t_call
            nore.append(got[:5])
        narr = np.asarray(nore, dtype=np.float64)
        print(
            "SPLIT_NORESET",
            " ".join("%s %.3f" % (names[k], float(np.median(narr[:, k]))) for k in range(5)),
            "interval %.3f" % float(np.median(intervals)),
            flush=True,
        )
        np.savez("/tmp/edgeai_bench/v6_split.npz", reset_each=arr, no_reset=narr, no_reset_interval_ms=np.asarray(intervals))

        for div1 in (15, 12, 10, 9, 8):
            mhz, reg = clk.set_div1(div1)
            print("CLOCK div1 %d mhz %.3f reg 0x%08x" % (div1, mhz, reg), flush=True)
            kat_run = run_set(dma, kat["payloads"], kat_g, len(kat_g), True)
            if kat_run is None:
                print("KAT_FAIL div1", div1, flush=True)
                return 5
            full = run_set(dma, payloads, golden, n1000, True)
            if full is None:
                print("N1000_FAIL div1", div1, flush=True)
                return 5
            windows, max_lsb = full
            med = float(np.median(windows))
            p99 = float(np.quantile(windows, 0.99))
            lines.append("%.4f,%.4f,%.4f,%d,%d" % (mhz, med, p99, max_lsb, div1))
            print("LADDER %.3f MHz window %.3f p99 %.3f max_lsb %d" % (mhz, med, p99, max_lsb), flush=True)

        top = 8
        mhz, reg = clk.set_div1(top)
        print("SOAK_CLOCK %.3f" % mhz, flush=True)
        n10 = min(10000, len(payloads), len(golden))
        big = run_set(dma, payloads, golden, n10, True)
        if big is None:
            print("N10K_FAIL", flush=True)
            return 5
        print("N10K_OK median %.3f" % float(np.median(big[0])), flush=True)
        deadline = time.perf_counter() + float(os.environ.get("SOAK_S", "1800"))
        seen = 0
        checked = 0
        while time.perf_counter() < deadline:
            idx = seen % n10
            got = one_frame(dma, payload_of(payloads[idx]), True)
            if got is None:
                return 3
            lsb = got[5]
            if got[6]:
                print("AA soak", seen, flush=True)
                return 4
            if seen % 100 == 0:
                err = int(np.abs(lsb - golden[idx]).max())
                checked += 1
                if err:
                    print("SOAK_MISMATCH", seen, idx, err, flush=True)
                    return 5
            seen += 1
            if seen % 20000 == 0:
                print("soak", seen, "checked", checked, flush=True)
        print("SOAK_DONE", seen, checked, "mhz", mhz, flush=True)
        open("/tmp/edgeai_bench/ladder.csv", "w").write("\n".join(lines) + "\n")
        return 0
    finally:
        try:
            mhz, reg = clk.set_div1(15)
            print("RESTORED div1 15 mhz %.3f reg 0x%08x" % (mhz, reg), flush=True)
        except Exception as exc:
            print("RESTORE_FAIL", exc, flush=True)
        clk.close()
        dma.close()
        open("/tmp/edgeai_bench/ladder.csv", "w").write("\n".join(lines) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
