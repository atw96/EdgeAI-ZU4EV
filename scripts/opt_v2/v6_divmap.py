#!/usr/bin/env python3
"""Map which PL0 divisors actually change the measured window. Does not touch DMA in set mode.

set <div1> allows 10..15 only. win <n> measures n frames at the already loaded fabric.
"""
import mmap
import os
import struct
import sys
import time

import numpy as np

from dma_infer_common import DST_PHYS, OUT_BYTES, SRC_PHYS, DevMemDma, require_pl_operating

PARENT_HZ = 1499135828.0
PL0_PAGE = 0xFF5E0000
PL0_OFF = 0xC0
DIV1_MASK = 0x3F00


def describe(val):
    div0 = (val >> 16) & 0x3F
    div1 = (val >> 8) & 0x3F
    mhz = PARENT_HZ / (div0 * div1) / 1e6 if div0 and div1 else 0.0
    return div0, div1, mhz


def pl0_mmap():
    fd = os.open("/dev/mem", os.O_RDWR | os.O_SYNC)
    mm = mmap.mmap(fd, 0x1000, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE, offset=PL0_PAGE)
    return fd, mm


def as_lsb(arr):
    a = np.asarray(arr)
    if a.dtype.kind == "f":
        return np.rint(a.astype(np.float64) * 1024.0).astype(np.int32)
    return a.astype(np.int32)


def cmd_set(div1):
    div1 = int(div1)
    if div1 < 10 or div1 > 15:
        print("DIV_REJECT", div1, flush=True)
        return 2
    fd, mm = pl0_mmap()
    try:
        cur = struct.unpack_from("<I", mm, PL0_OFF)[0]
        val = (cur & ~DIV1_MASK) | ((div1 & 0x3F) << 8)
        struct.pack_into("<I", mm, PL0_OFF, val)
        time.sleep(0.01)
        got = struct.unpack_from("<I", mm, PL0_OFF)[0]
    finally:
        mm.close()
        os.close(fd)
    div0, back, mhz = describe(got)
    print("SET div1 %d readback %d mhz %.4f reg 0x%08x" % (div1, back, mhz, got), flush=True)
    return 0 if back == div1 and div0 == 1 else 2


def cmd_read():
    fd, mm = pl0_mmap()
    try:
        got = struct.unpack_from("<I", mm, PL0_OFF)[0]
    finally:
        mm.close()
        os.close(fd)
    div0, div1, mhz = describe(got)
    print("READ div0 %d div1 %d mhz %.4f reg 0x%08x" % (div0, div1, mhz, got), flush=True)
    return 0


def cmd_win(n):
    require_pl_operating()
    n = int(n)
    bench = np.load(os.environ["BENCH_NPZ"])
    golden = as_lsb(np.load(os.environ["GOLDEN_NPY"]))
    payloads = bench["payloads"]
    dma = DevMemDma()
    windows = []
    max_lsb = 0
    aa = 0
    try:
        for i in range(n):
            if not dma.soft_reset():
                print("RESET_FAIL", i, flush=True)
                return 3
            dma.clear_ioc()
            dma.flush_write(DST_PHYS, b"\xAA" * OUT_BYTES)
            row = payloads[i]
            dma.flush_write(SRC_PHYS, row.tobytes() if isinstance(row, np.ndarray) else bytes(row))
            t0 = time.perf_counter()
            dma.start_transfer()
            ok, _, _, why = dma.wait_ioc()
            dt = (time.perf_counter() - t0) * 1000.0
            if not ok:
                print("FAIL", why, flush=True)
                return 3
            raw = dma.inv_read(DST_PHYS, OUT_BYTES, after_dma=True)
            holes = 0
            for k in range(24):
                if raw[k * 4 + 2] == 0xAA and raw[k * 4 + 3] == 0xAA:
                    holes += 1
            if holes:
                aa += 1
                print("AA", i, holes, raw.hex(), flush=True)
            gap = np.asarray(dma.decode_gap_features(raw), dtype=np.float64)
            lsb = np.rint(gap * 1024.0).astype(np.int32)
            err = int(np.abs(lsb - golden[i]).max())
            if err > max_lsb:
                max_lsb = err
            windows.append(dt)
        arr = np.asarray(windows)
        print(
            "WIN n %d median %.4f p99 %.4f max_lsb %d aa %d" % (n, float(np.median(arr)), float(np.quantile(arr, 0.99)), max_lsb, aa),
            flush=True,
        )
        return 5 if max_lsb or aa else 0
    finally:
        dma.close()


def main():
    cmd = sys.argv[1]
    if cmd == "set":
        return cmd_set(sys.argv[2])
    if cmd == "read":
        return cmd_read()
    if cmd == "win":
        return cmd_win(sys.argv[2])
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
