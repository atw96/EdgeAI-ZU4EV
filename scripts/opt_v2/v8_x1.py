#!/usr/bin/env python3
"""X1 busy-wait clock ladder. setdiv does not touch DMA.

The host must reload the bitstream after every setdiv and before measure.
Allowed DIVISOR0: 15, 12, 11, 10, 9, 8. DIVISOR1 stays 1.
"""
import json
import mmap
import os
import struct
import sys
import time

import numpy as np

from dma_infer_common import (
    DMA,
    DST_PHYS,
    ERR_MASK,
    IN_BYTES,
    IOC,
    MM2S_CR,
    MM2S_LEN,
    MM2S_SA,
    MM2S_SA_MSB,
    MM2S_SR,
    OUT_BYTES,
    S2MM_CR,
    S2MM_DA,
    S2MM_DA_MSB,
    S2MM_LEN,
    S2MM_SR,
    SRC_PHYS,
    DevMemDma,
    decode_gap_raw,
    require_pl_operating,
)

PARENT_HZ = 1499135828.0
PL0_PAGE = 0xFF5E0000
PL0_OFF = 0xC0
DIV0_MASK = 0x3F00
ALLOWED = {15, 12, 11, 10, 9, 8}
WAIT0_MS = 1.719
F0_MHZ = 99.942


def as_lsb(arr):
    a = np.asarray(arr)
    if a.dtype.kind == "f":
        return np.rint(a.astype(np.float64) * 1024.0).astype(np.int32)
    return a.astype(np.int32)


def payload_of(row):
    return row.tobytes() if isinstance(row, np.ndarray) else bytes(row)


def lsb_of(raw):
    gap = np.asarray(decode_gap_raw(raw), dtype=np.float64)
    return np.rint(gap * 1024.0).astype(np.int32)


def hole_channels(raw):
    return [k for k in range(24) if raw[k * 4 + 2] == 0xAA and raw[k * 4 + 3] == 0xAA]


def decode_reg(val):
    return {
        "word": "0x%08x" % val,
        "DIVISOR0": (val >> 8) & 0x3F,
        "DIVISOR1": (val >> 16) & 0x3F,
        "CLKACT": (val >> 24) & 1,
        "SRCSEL": val & 7,
    }


def mhz_of(info):
    d0, d1 = info["DIVISOR0"], info["DIVISOR1"]
    if not d0 or not d1:
        return 0.0
    return PARENT_HZ / (d0 * d1) / 1e6


def pl0_open(write):
    flags = os.O_RDWR | os.O_SYNC if write else os.O_RDONLY | os.O_SYNC
    prot = mmap.PROT_READ | mmap.PROT_WRITE if write else mmap.PROT_READ
    fd = os.open("/dev/mem", flags)
    mm = mmap.mmap(fd, 0x1000, mmap.MAP_SHARED, prot, offset=PL0_PAGE)
    return fd, mm


def read_pl0():
    fd, mm = pl0_open(False)
    try:
        return struct.unpack_from("<I", mm, PL0_OFF)[0]
    finally:
        mm.close()
        os.close(fd)


def cmd_readreg():
    info = decode_reg(read_pl0())
    info["mhz"] = round(mhz_of(info), 4)
    print("REG", json.dumps(info), flush=True)
    expect = int(os.environ.get("EXPECT_DIV0", "0"))
    if expect and info["DIVISOR0"] != expect:
        print("DIV_MISMATCH", info["DIVISOR0"], expect, flush=True)
        return 6
    if info["DIVISOR1"] != 1 or info["CLKACT"] != 1:
        print("DIV1_OR_CLKACT", flush=True)
        return 6
    return 0


def cmd_setdiv(div0):
    div0 = int(div0)
    if div0 not in ALLOWED:
        print("DIV_REJECT", div0, flush=True)
        return 2
    fd, mm = pl0_open(True)
    try:
        cur = struct.unpack_from("<I", mm, PL0_OFF)[0]
        val = (cur & ~DIV0_MASK) | ((div0 & 0x3F) << 8)
        struct.pack_into("<I", mm, PL0_OFF, val)
        time.sleep(0.01)
        got = struct.unpack_from("<I", mm, PL0_OFF)[0]
    finally:
        mm.close()
        os.close(fd)
    info = decode_reg(got)
    print("SET", json.dumps(info), "mhz", "%.4f" % mhz_of(info), flush=True)
    if info["DIVISOR0"] != div0 or info["DIVISOR1"] != 1:
        return 2
    return 0


def ensure_idle(dma):
    for _ in range(3):
        dma.clear_ioc()
        s2mm = dma.rd(DMA + S2MM_SR)
        mm2s = dma.rd(DMA + MM2S_SR)
        if not (s2mm & IOC) and not (mm2s & IOC) and not (s2mm & ERR_MASK) and not (mm2s & ERR_MASK):
            return True
        if not dma.soft_reset():
            print("RESET_FAIL", "0x%08x" % s2mm, flush=True)
            return False
        dma.clear_ioc()
    print(
        "IOC_STUCK",
        "0x%08x" % dma.rd(DMA + S2MM_SR),
        "0x%08x" % dma.rd(DMA + MM2S_SR),
        flush=True,
    )
    return False


def start_at(dma):
    dma.wr(DMA + S2MM_DA, DST_PHYS)
    dma.wr(DMA + S2MM_DA_MSB, 0)
    dma.wr(DMA + S2MM_CR, dma.rd(DMA + S2MM_CR) | 0x1)
    dma.wr(DMA + S2MM_LEN, OUT_BYTES)
    dma.wr(DMA + MM2S_SA, SRC_PHYS)
    dma.wr(DMA + MM2S_SA_MSB, 0)
    dma.wr(DMA + MM2S_CR, dma.rd(DMA + MM2S_CR) | 0x1)
    dma.wr(DMA + MM2S_LEN, IN_BYTES)


def wait_ioc(dma):
    timeout_s = float(os.environ.get("DMA_IOC_TIMEOUT_S", "8"))
    deadline = time.perf_counter() + timeout_s
    while time.perf_counter() < deadline:
        s2mm = dma.rd(DMA + S2MM_SR)
        mm2s = dma.rd(DMA + MM2S_SR)
        if (s2mm & ERR_MASK) or (mm2s & ERR_MASK):
            return False, mm2s, s2mm, "ERR"
        if (s2mm & IOC) and (mm2s & IOC):
            return True, mm2s, s2mm, "IOC"
    return False, dma.rd(DMA + MM2S_SR), dma.rd(DMA + S2MM_SR), "TIMEOUT"


def one_frame(dma, payload):
    if not dma.soft_reset():
        return None
    if not ensure_idle(dma):
        return None
    dma.flush_write(DST_PHYS, b"\xAA" * OUT_BYTES)
    dma.flush_write(SRC_PHYS, payload)
    t0 = time.perf_counter()
    start_at(dma)
    t1 = time.perf_counter()
    ok, mm2s, s2mm, why = wait_ioc(dma)
    t2 = time.perf_counter()
    if not ok:
        print("FAIL", why, "s2mm", "0x%08x" % s2mm, "mm2s", "0x%08x" % mm2s, flush=True)
        return None
    raw = dma.inv_read(DST_PHYS, OUT_BYTES, after_dma=True)
    length = dma.rd(DMA + S2MM_LEN)
    return (t1 - t0) * 1000.0, (t2 - t1) * 1000.0, raw, length, s2mm


def run_set(payloads, golden, n, tag):
    require_pl_operating()
    info = decode_reg(read_pl0())
    mhz = mhz_of(info)
    pred = WAIT0_MS * F0_MHZ / mhz if mhz else 0.0
    dma = DevMemDma()
    waits = []
    windows = []
    max_lsb = 0
    try:
        if not dma.soft_reset():
            return 3
        for i in range(n):
            got = one_frame(dma, payload_of(payloads[i]))
            if got is None:
                return 3
            start_ms, wait_ms, raw, length, s2mm = got
            holes = hole_channels(raw)
            lsb = lsb_of(raw)
            err = int(np.abs(lsb - golden[i]).max())
            if err > max_lsb:
                max_lsb = err
            if holes or err or length != OUT_BYTES or (s2mm & ERR_MASK):
                print(
                    "MISMATCH",
                    tag,
                    i,
                    "lsb",
                    err,
                    "holes",
                    holes,
                    "len",
                    length,
                    "s2mm",
                    "0x%08x" % s2mm,
                    flush=True,
                )
                return 5
            waits.append(wait_ms)
            windows.append(start_ms + wait_ms)
            if n >= 2000 and i and i % 2000 == 0:
                print("progress", tag, i, flush=True)
        w = np.asarray(waits)
        win = np.asarray(windows)
        rel = (float(np.median(w)) - pred) / pred if pred else 0.0
        row = {
            "tag": tag,
            "div0": info["DIVISOR0"],
            "div1": info["DIVISOR1"],
            "f_mhz": round(mhz, 4),
            "n": n,
            "wait_ms": round(float(np.median(w)), 4),
            "p99_wait_ms": round(float(np.quantile(w, 0.99)), 4),
            "window_ms": round(float(np.median(win)), 4),
            "p99_window_ms": round(float(np.quantile(win, 0.99)), 4),
            "max_lsb": max_lsb,
            "pred_wait_ms": round(pred, 4),
            "rel_err": round(rel, 4),
        }
        print("POINT", json.dumps(row), flush=True)
        path = os.environ.get("LADDER_CSV", "/tmp/edgeai_bench/v8_ladder.csv")
        new = not os.path.isfile(path)
        with open(path, "a") as fh:
            if new:
                fh.write("f_mhz,wait_ms,window_ms,p99_wait_ms,p99_window_ms,max_lsb,div0,n,tag\n")
            fh.write(
                "%.4f,%.4f,%.4f,%.4f,%.4f,%d,%d,%d,%s\n"
                % (
                    row["f_mhz"],
                    row["wait_ms"],
                    row["window_ms"],
                    row["p99_wait_ms"],
                    row["p99_window_ms"],
                    row["max_lsb"],
                    row["div0"],
                    row["n"],
                    tag,
                )
            )
        if os.environ.get("SAVE_NPZ"):
            np.savez(
                os.environ["SAVE_NPZ"],
                wait_ms=w,
                window_ms=win,
            )
        return 0
    finally:
        dma.close()


def load_bench():
    bench = np.load(os.environ["BENCH_NPZ"])
    golden = as_lsb(np.load(os.environ["GOLDEN_NPY"]))
    return bench["payloads"], golden


def cmd_kat():
    kat = np.load(os.environ["KAT_NPZ"])
    golden = as_lsb(np.load(os.environ["KAT_GOLDEN"])["gap"])
    n = min(len(kat["payloads"]), len(golden))
    return run_set(kat["payloads"], golden, n, "kat")


def cmd_n(n, tag):
    payloads, golden = load_bench()
    n = min(int(n), len(payloads), len(golden))
    return run_set(payloads, golden, n, tag)


def main():
    cmd = sys.argv[1]
    if cmd == "readreg":
        return cmd_readreg()
    if cmd == "setdiv":
        return cmd_setdiv(sys.argv[2])
    if cmd == "kat":
        return cmd_kat()
    if cmd == "n1000":
        return cmd_n(1000, "n1000")
    if cmd == "n10k":
        return cmd_n(10000, sys.argv[2])
    print("unknown", cmd, flush=True)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
