#!/usr/bin/env python3
"""One clock-ladder step. The host reloads the bitstream after every divisor write.

Subcommands: read, set <div1>, split, kat, n1000, n10k, soak
set only accepts 15, 12, 10, 9, 8. It does not touch DMA.
"""
import os
import struct
import sys
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
ALLOWED = {15, 12, 10, 9, 8}


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


def pl0_read():
    fd = os.open("/dev/mem", os.O_RDWR | os.O_SYNC)
    try:
        mm = mmap.mmap(fd, 0x1000, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE, offset=PL0_PAGE)
        try:
            return struct.unpack_from("<I", mm, PL0_OFF)[0]
        finally:
            mm.close()
    finally:
        os.close(fd)


def describe(val):
    div0 = (val >> 16) & 0x3F
    div1 = (val >> 8) & 0x3F
    mhz = PARENT_HZ / (div0 * div1) / 1e6 if div0 and div1 else 0.0
    return div0, div1, mhz


def cmd_read():
    val = pl0_read()
    div0, div1, mhz = describe(val)
    print("READ div0 %d div1 %d mhz %.4f reg 0x%08x" % (div0, div1, mhz, val), flush=True)
    return 0


def cmd_set(div1):
    div1 = int(div1)
    if div1 not in ALLOWED:
        print("DIV_REJECT", div1, flush=True)
        return 2
    fd = os.open("/dev/mem", os.O_RDWR | os.O_SYNC)
    mm = mmap.mmap(fd, 0x1000, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE, offset=PL0_PAGE)
    try:
        cur = struct.unpack_from("<I", mm, PL0_OFF)[0]
        val = (cur & ~DIV1_MASK) | ((div1 & 0x3F) << 8)
        struct.pack_into("<I", mm, PL0_OFF, val)
        time.sleep(0.01)
        got = struct.unpack_from("<I", mm, PL0_OFF)[0]
    finally:
        mm.close()
        os.close(fd)
    back = (got >> 8) & 0x3F
    div0, _, mhz = describe(got)
    print("SET div1 %d readback %d mhz %.4f reg 0x%08x" % (div1, back, mhz, got), flush=True)
    return 0 if back == div1 and div0 == 1 else 2


def one_frame(dma, payload, do_reset):
    t0 = time.perf_counter()
    if do_reset and not dma.soft_reset():
        return None
    t_reset = (time.perf_counter() - t0) * 1000.0 if do_reset else 0.0
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


def load_bench():
    bench = np.load(os.environ["BENCH_NPZ"])
    golden = as_lsb(np.load(os.environ["GOLDEN_NPY"]))
    return bench["payloads"], golden


def run_n(dma, payloads, golden, n, do_reset, label):
    windows = []
    max_lsb = 0
    for i in range(n):
        got = one_frame(dma, payload_of(payloads[i]), do_reset)
        if got is None:
            return None
        window = got[2]
        lsb = got[5]
        if got[6]:
            print("AA", label, i, flush=True)
            return None
        err = int(np.abs(lsb - golden[i]).max())
        if err > max_lsb:
            max_lsb = err
        windows.append(window)
        if max_lsb:
            print("MISMATCH", label, i, max_lsb, flush=True)
            return None
    return np.asarray(windows, dtype=np.float64), max_lsb


def cmd_split():
    require_pl_operating()
    payloads, golden = load_bench()
    dma = DevMemDma()
    try:
        rows = []
        max_lsb = 0
        for i in range(200):
            got = one_frame(dma, payload_of(payloads[i]), True)
            if got is None:
                return 3
            err = int(np.abs(got[5] - golden[i]).max())
            if got[6] or err:
                print("SPLIT_MISMATCH", i, err, got[6], flush=True)
                return 5
            max_lsb = max(max_lsb, err)
            rows.append(got[:5])
        arr = np.asarray(rows, dtype=np.float64)
        names = ("reset", "flush", "window", "read", "dense")
        print(
            "SPLIT_RESET",
            " ".join("%s %.3f" % (names[k], float(np.median(arr[:, k]))) for k in range(5)),
            "max_lsb", max_lsb,
            flush=True,
        )
        nore = []
        intervals = []
        t_prev = None
        for i in range(100):
            t_call = time.perf_counter()
            got = one_frame(dma, payload_of(payloads[i]), False)
            if got is None:
                return 3
            err = int(np.abs(got[5] - golden[i]).max())
            if got[6] or err:
                print("NORESET_MISMATCH", i, err, got[6], flush=True)
                return 5
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
        np.savez(
            "/tmp/edgeai_bench/v6_split.npz",
            reset_each=arr,
            no_reset=narr,
            no_reset_interval_ms=np.asarray(intervals),
        )
        return 0
    finally:
        dma.close()


def cmd_counted(n, label):
    require_pl_operating()
    if label == "kat":
        kat = np.load(os.environ["KAT_NPZ"])
        payloads = kat["payloads"]
        golden = as_lsb(np.load(os.environ["KAT_GOLDEN"])["gap"])
        n = min(n, len(payloads), len(golden))
    else:
        payloads, golden = load_bench()
        n = min(n, len(payloads), len(golden))
    val = pl0_read()
    _, div1, mhz = describe(val)
    dma = DevMemDma()
    try:
        got = run_n(dma, payloads, golden, n, True, label)
        if got is None:
            print("STEP_FAIL", label, "div1", div1, flush=True)
            return 5
        windows, max_lsb = got
        med = float(np.median(windows))
        p99 = float(np.quantile(windows, 0.99))
        line = "%.4f,%.4f,%.4f,%d,%d" % (mhz, med, p99, max_lsb, div1)
        print("LADDER", label, "n", n, line, flush=True)
        if label != "kat":
            with open("/tmp/edgeai_bench/ladder.csv", "a") as fh:
                fh.write(line + "\n")
        return 0
    finally:
        dma.close()


def cmd_soak():
    require_pl_operating()
    payloads, golden = load_bench()
    n10 = min(10000, len(payloads), len(golden))
    val = pl0_read()
    _, div1, mhz = describe(val)
    deadline = time.perf_counter() + float(os.environ.get("SOAK_S", "1800"))
    dma = DevMemDma()
    seen = 0
    checked = 0
    try:
        while time.perf_counter() < deadline:
            idx = seen % n10
            got = one_frame(dma, payload_of(payloads[idx]), True)
            if got is None:
                return 3
            if got[6]:
                print("AA soak", seen, flush=True)
                return 4
            if seen % 100 == 0:
                err = int(np.abs(got[5] - golden[idx]).max())
                checked += 1
                if err:
                    print("SOAK_MISMATCH", seen, idx, err, flush=True)
                    return 5
            seen += 1
            if seen % 20000 == 0:
                print("soak", seen, "checked", checked, "mhz", "%.3f" % mhz, flush=True)
        print("SOAK_DONE", seen, checked, "div1", div1, "mhz", "%.4f" % mhz, flush=True)
        return 0
    finally:
        dma.close()


def main():
    cmd = sys.argv[1]
    if cmd == "read":
        return cmd_read()
    if cmd == "set":
        return cmd_set(sys.argv[2])
    if cmd == "split":
        return cmd_split()
    if cmd == "kat":
        return cmd_counted(19, "kat")
    if cmd == "n1000":
        return cmd_counted(1000, "n1000")
    if cmd == "n10k":
        return cmd_counted(10000, "n10k")
    if cmd == "soak":
        return cmd_soak()
    print("unknown", cmd, flush=True)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
