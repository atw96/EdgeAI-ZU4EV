#!/usr/bin/env python3
"""W1 at the clock the board already has. Does not write PL0_REF_CTRL.

Subcommands: readreg, budget, stress, align, soak
"""
import json
import os
import struct
import sys
import time
from collections import deque

import mmap
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
    apply_ps_dense,
    decode_gap_raw,
    require_pl_operating,
)

PL0_PAGE = 0xFF5E0000
PL0_OFF = 0xC0
OUT_JSON = "/tmp/edgeai_bench/v7_w1.json"
EVENTS = "/tmp/edgeai_bench/v7_events.jsonl"


def as_lsb(arr):
    a = np.asarray(arr)
    if a.dtype.kind == "f":
        return np.rint(a.astype(np.float64) * 1024.0).astype(np.int32)
    return a.astype(np.int32)


def payload_of(row):
    return row.tobytes() if isinstance(row, np.ndarray) else bytes(row)


def aa_offsets(raw):
    return [i for i, b in enumerate(raw) if b == 0xAA]


def hole_channels(raw):
    return [k for k in range(24) if len(raw) > k * 4 + 3 and raw[k * 4 + 2] == 0xAA and raw[k * 4 + 3] == 0xAA]


def lsb_of(raw):
    gap = np.asarray(decode_gap_raw(raw), dtype=np.float64)
    return np.rint(gap * 1024.0).astype(np.int32)


def sr_bits(sr):
    return {
        "raw": "0x%08x" % sr,
        "halted": int(bool(sr & 0x1)),
        "idle": int(bool(sr & 0x2)),
        "dmainterr": int(bool(sr & 0x10)),
        "dmaslverr": int(bool(sr & 0x20)),
        "dmadecerr": int(bool(sr & 0x40)),
        "ioc": int(bool(sr & IOC)),
    }


def load_io():
    bench = np.load(os.environ["BENCH_NPZ"])
    golden = as_lsb(np.load(os.environ["GOLDEN_NPY"]))
    return bench["payloads"], golden


def read_pl0():
    fd = os.open("/dev/mem", os.O_RDONLY | os.O_SYNC)
    try:
        mm = mmap.mmap(fd, 0x1000, mmap.MAP_SHARED, mmap.PROT_READ, offset=PL0_PAGE)
        try:
            return struct.unpack_from("<I", mm, PL0_OFF)[0]
        finally:
            mm.close()
    finally:
        os.close(fd)


def cmd_readreg():
    val = read_pl0()
    divisor0 = (val >> 8) & 0x3F
    divisor1 = (val >> 16) & 0x3F
    srcsel = val & 0x7
    clkact = (val >> 24) & 0x1
    print(
        "REG 0x%08x DIVISOR0 %d DIVISOR1 %d CLKACT %d SRCSEL %d" % (val, divisor0, divisor1, clkact, srcsel),
        flush=True,
    )
    if divisor0 != 15 or divisor1 != 1 or clkact != 1:
        print("CLOCK_NOT_100", flush=True)
        return 6
    return 0


def start_at(dma, dst):
    dma.wr(DMA + S2MM_DA, dst & 0xFFFFFFFF)
    dma.wr(DMA + S2MM_DA_MSB, 0)
    dma.wr(DMA + S2MM_CR, dma.rd(DMA + S2MM_CR) | 0x1)
    dma.wr(DMA + S2MM_LEN, OUT_BYTES)
    dma.wr(DMA + MM2S_SA, SRC_PHYS)
    dma.wr(DMA + MM2S_SA_MSB, 0)
    dma.wr(DMA + MM2S_CR, dma.rd(DMA + MM2S_CR) | 0x1)
    dma.wr(DMA + MM2S_LEN, IN_BYTES)


def wait_ioc(dma, poll_s):
    timeout_s = float(os.environ.get("DMA_IOC_TIMEOUT_S", "8"))
    deadline = time.perf_counter() + timeout_s
    polls = 0
    while time.perf_counter() < deadline:
        if poll_s:
            time.sleep(poll_s)
        polls += 1
        s2mm = dma.rd(DMA + S2MM_SR)
        mm2s = dma.rd(DMA + MM2S_SR)
        if (s2mm & ERR_MASK) or (mm2s & ERR_MASK):
            return False, mm2s, s2mm, "ERR", polls
        if (s2mm & IOC) and (mm2s & IOC):
            return True, mm2s, s2mm, "IOC", polls
    return False, dma.rd(DMA + MM2S_SR), dma.rd(DMA + S2MM_SR), "TIMEOUT", polls


def capture(dma, dst, raw0, prev, seen, mode, mm2s, s2mm):
    raw_now = dma.inv_read(dst, OUT_BYTES, after_dma=False)
    raw_inv = dma.inv_read(dst, OUT_BYTES, after_dma=True)
    time.sleep(10e-6)
    raw_10us = dma.inv_read(dst, OUT_BYTES, after_dma=True)
    time.sleep(0.001)
    raw_1ms = dma.inv_read(dst, OUT_BYTES, after_dma=True)
    rec = {
        "frame": seen,
        "ts": time.time(),
        "mode": mode,
        "dst": "0x%08x" % dst,
        "dst_mod64": dst % 64,
        "mm2s": sr_bits(mm2s),
        "s2mm": sr_bits(s2mm),
        "s2mm_len": dma.rd(DMA + S2MM_LEN),
        "first_aa_bytes": aa_offsets(raw0),
        "reread_plain_aa_bytes": aa_offsets(raw_now),
        "reread_inv_aa_bytes": aa_offsets(raw_inv),
        "reread_10us_aa_bytes": aa_offsets(raw_10us),
        "reread_1ms_aa_bytes": aa_offsets(raw_1ms),
        "first_hex": raw0.hex(),
        "plain_hex": raw_now.hex(),
        "inv_hex": raw_inv.hex(),
        "us10_hex": raw_10us.hex(),
        "ms1_hex": raw_1ms.hex(),
        "prev3_hex": list(prev),
    }
    with open(EVENTS, "a") as fh:
        fh.write(json.dumps(rec) + "\n")
    print(
        "EVENT",
        seen,
        mode,
        "dst_mod64",
        dst % 64,
        "aa",
        rec["first_aa_bytes"],
        "plain",
        rec["reread_plain_aa_bytes"],
        "inv",
        rec["reread_inv_aa_bytes"],
        "us10",
        rec["reread_10us_aa_bytes"],
        "ms1",
        rec["reread_1ms_aa_bytes"],
        "s2mm_len",
        rec["s2mm_len"],
        "s2mm",
        rec["s2mm"]["raw"],
        flush=True,
    )
    return rec


def append_summary(row):
    rows = []
    if os.path.isfile(OUT_JSON):
        try:
            rows = json.load(open(OUT_JSON))
        except ValueError:
            rows = []
    rows.append(row)
    with open(OUT_JSON, "w") as fh:
        json.dump(rows, fh, indent=2)
    print("SUMMARY", json.dumps(row), flush=True)


def run_loop(dma, payloads, golden, n, dst, do_reset, poll_s, poison, invalidate, mode, deadline=None):
    prev = deque(maxlen=3)
    events = []
    parts = []
    intervals = []
    max_lsb = 0
    t_prev = None
    tail = None
    seen = 0
    if do_reset and not dma.soft_reset():
        print("RESET_FAIL", flush=True)
        return None
    dma.clear_ioc()
    while True:
        if deadline is not None and time.perf_counter() >= deadline:
            break
        if deadline is None and seen >= n:
            break
        idx = seen % min(len(payloads), len(golden))
        t_loop = time.perf_counter()
        if t_prev is not None:
            intervals.append((t_loop - t_prev) * 1000.0)
        t_prev = t_loop
        marks = [t_loop]
        if do_reset:
            if not dma.soft_reset():
                print("RESET_FAIL", seen, flush=True)
                return None
            dma.clear_ioc()
        marks.append(time.perf_counter())
        if poison:
            dma.flush_write(dst, b"\xAA" * OUT_BYTES)
        marks.append(time.perf_counter())
        dma.flush_write(SRC_PHYS, payload_of(payloads[idx]))
        marks.append(time.perf_counter())
        start_at(dma, dst)
        marks.append(time.perf_counter())
        ok, mm2s, s2mm, why, polls = wait_ioc(dma, poll_s)
        marks.append(time.perf_counter())
        if not ok:
            print("FAIL", seen, why, "s2mm", "0x%08x" % s2mm, flush=True)
            return None
        raw = dma.inv_read(dst, OUT_BYTES, after_dma=invalidate)
        marks.append(time.perf_counter())
        lsb = lsb_of(raw)
        marks.append(time.perf_counter())
        apply_ps_dense((lsb.astype(np.float64) / 1024.0).tolist())
        marks.append(time.perf_counter())
        err = int(np.abs(lsb - golden[idx]).max())
        holes = hole_channels(raw)
        if err > max_lsb:
            max_lsb = err
        event = bool(holes) or (not poison and err)
        if event and len(events) < 8:
            events.append(capture(dma, dst, raw, prev, seen, mode, mm2s, s2mm))
        elif event:
            events.append({"frame": seen, "mode": mode, "aa": aa_offsets(raw)})
        prev.append(raw.hex())
        marks.append(time.perf_counter())
        names = ("reset", "poison", "src", "start", "wait", "read", "decode", "dense", "book")
        row_ms = [(marks[i + 1] - marks[i]) * 1000.0 for i in range(len(names))]
        row_ms.append(((t_loop - tail) * 1000.0) if tail is not None else 0.0)
        tail = marks[-1]
        parts.append(row_ms)
        seen += 1
        if seen % 20000 == 0:
            print("progress", mode, seen, "events", len(events), "max_lsb", max_lsb, flush=True)
        if len(events) >= 5 and events[0].get("reread_inv_aa_bytes") == [] and events[0].get("first_aa_bytes"):
            print("SYSTEMATIC", mode, "events", len(events), "frames", seen, flush=True)
            break
    arr = np.asarray(parts, dtype=np.float64) if parts else np.zeros((0, 10))
    name_list = ["reset", "poison", "src", "start", "wait", "read", "decode", "dense", "book", "between"]
    med = {name_list[i]: float(np.median(arr[:, i])) if len(arr) else 0.0 for i in range(10)}
    iv = np.asarray(intervals, dtype=np.float64) if intervals else np.zeros(0)
    sum_med = float(sum(med.values()))
    med_iv = float(np.median(iv)) if len(iv) else sum_med
    return {
        "mode": mode,
        "frames": seen,
        "events": len(events),
        "max_lsb": max_lsb,
        "dst": "0x%08x" % dst,
        "dst_mod64": dst % 64,
        "do_reset": bool(do_reset),
        "poll_s": poll_s,
        "poison": bool(poison),
        "invalidate": bool(invalidate),
        "median_ms": med,
        "sum_of_medians_ms": sum_med,
        "interval_ms": med_iv,
        "budget_gap_ms": med_iv - sum_med,
        "window_ms": med["wait"],
        "event_frames": [e.get("frame") for e in events],
    }


def cmd_budget():
    require_pl_operating()
    payloads, golden = load_io()
    dma = DevMemDma()
    rows = []
    try:
        specs = [
            ("budget_reset_poll500us", True, 0.0005),
            ("budget_noreset_poll500us", False, 0.0005),
            ("budget_reset_poll0", True, 0.0),
            ("budget_noreset_poll0", False, 0.0),
        ]
        for name, do_reset, poll in specs:
            print("BEGIN", name, flush=True)
            row = run_loop(dma, payloads, golden, 200, DST_PHYS, do_reset, poll, True, True, name)
            if row is None:
                return 3
            rows.append(row)
            append_summary(row)
            print(
                "BUDGET",
                name,
                "interval %.3f" % row["interval_ms"],
                "sum %.3f" % row["sum_of_medians_ms"],
                "gap %.3f" % row["budget_gap_ms"],
                "window %.3f" % row["window_ms"],
                "max_lsb",
                row["max_lsb"],
                "events",
                row["events"],
                flush=True,
            )
        return 0
    finally:
        dma.close()


def cmd_stress():
    require_pl_operating()
    payloads, golden = load_io()
    n = int(os.environ.get("STRESS_N", "30000"))
    dma = DevMemDma()
    try:
        specs = [
            ("stress_normal", True, True),
            ("stress_noinv", True, False),
            ("stress_noprefill", False, True),
        ]
        for name, poison, inv in specs:
            print("BEGIN", name, flush=True)
            row = run_loop(dma, payloads, golden, n, DST_PHYS, False, 0.0, poison, inv, name)
            if row is None:
                return 3
            append_summary(row)
        return 0
    finally:
        dma.close()


def cmd_align():
    require_pl_operating()
    payloads, golden = load_io()
    n = int(os.environ.get("ALIGN_N", "40000"))
    dma = DevMemDma()
    try:
        for mod in (0, 32, 16):
            dst = DST_PHYS + mod
            name = "align_mod%d" % mod
            print("BEGIN", name, "dst 0x%08x" % dst, flush=True)
            row = run_loop(dma, payloads, golden, n, dst, False, 0.0, True, True, name)
            if row is None:
                return 3
            append_summary(row)
        return 0
    finally:
        dma.close()


def cmd_soak():
    require_pl_operating()
    payloads, golden = load_io()
    seconds = float(os.environ.get("SOAK_S", "1800"))
    dma = DevMemDma()
    try:
        print("BEGIN soak_noreset", flush=True)
        row = run_loop(
            dma,
            payloads,
            golden,
            0,
            DST_PHYS,
            False,
            0.0,
            True,
            True,
            "soak_noreset",
            deadline=time.perf_counter() + seconds,
        )
        if row is None:
            return 3
        append_summary(row)
        print("SOAK_DONE", row["frames"], "events", row["events"], "max_lsb", row["max_lsb"], flush=True)
        return 4 if row["events"] else 0
    finally:
        dma.close()


def main():
    cmd = sys.argv[1]
    if cmd == "readreg":
        return cmd_readreg()
    if cmd == "budget":
        return cmd_budget()
    if cmd == "stress":
        return cmd_stress()
    if cmd == "align":
        return cmd_align()
    if cmd == "soak":
        return cmd_soak()
    print("unknown", cmd, flush=True)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
