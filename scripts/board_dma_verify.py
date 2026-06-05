#!/usr/bin/env python3
"""Single board DMA verification: GPIO + CMA + masked DMACR + PG021/driver init + loopback."""
import ctypes
import hashlib
import mmap
import os
import struct
import sys
import time

DMA = 0x80040000
GPIO = 0x80090000
SRC = 0x66C00000
DST = 0x66C01000
TEST_LEN = 64

MM2S_CR, MM2S_SR = 0x00, 0x04
MM2S_SA, MM2S_SA_MSB, MM2S_LEN = 0x18, 0x1C, 0x28
S2MM_CR, S2MM_SR = 0x30, 0x34
S2MM_DA, S2MM_DA_MSB, S2MM_LEN = 0x48, 0x4C, 0x58

IOC = 1 << 12
ERR_MASK = 0x770
# DMACR bit1 is RO=1 per PG021; compare RS + user-writable bits only
DMACR_MASK = 0x00017007


def open_mm(base, size=0x1000):
    fd = os.open("/dev/mem", os.O_RDWR | os.O_SYNC)
    mm = mmap.mmap(fd, size, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE, offset=base)
    return fd, mm


def rd32(mm, off):
    return struct.unpack("<I", mm[off : off + 4])[0]


def wr32(mm, off, val):
    mm[off : off + 4] = struct.pack("<I", val)


def test_gpio():
    fd, mm = open_mm(GPIO)
    orig = rd32(mm, 0)
    wr32(mm, 0, orig ^ 1)
    got = rd32(mm, 0)
    wr32(mm, 0, orig)
    mm.close()
    os.close(fd)
    ok = got == (orig ^ 1)
    print("GPIO @0x80090000: orig=0x%08X toggle=0x%08X %s" % (orig, got, "OK" if ok else "FAIL"))
    return ok


def cma_rw(phys, data):
    fd = os.open("/dev/mem", os.O_RDWR | os.O_SYNC)
    mm = mmap.mmap(fd, len(data), mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE, offset=phys)
    mm[:] = data
    lib = ctypes.CDLL("libc.so.6")
    ptr = ctypes.cast(ctypes.addressof(ctypes.c_char.from_buffer(mm)), ctypes.c_void_p)
    lib.msync(ptr, len(data), 4)
    lib.madvise(ptr, len(data), 4)
    got = bytes(mm[: len(data)])
    mm.close()
    os.close(fd)
    return got == data


def soft_reset(mm):
    wr32(mm, MM2S_CR, rd32(mm, MM2S_CR) | 0x4)
    wr32(mm, S2MM_CR, rd32(mm, S2MM_CR) | 0x4)
    for _ in range(500):
        if not (rd32(mm, MM2S_CR) & 0x4) and not (rd32(mm, S2MM_CR) & 0x4):
            return True
        time.sleep(0.002)
    return False


def try_sa_write(mm, label, rs_before=True):
    if rs_before:
        wr32(mm, MM2S_CR, (rd32(mm, MM2S_CR) & ~DMACR_MASK) | 0x1)
    else:
        wr32(mm, MM2S_CR, rd32(mm, MM2S_CR) & ~0x1)
    wr32(mm, MM2S_SA, SRC)
    wr32(mm, MM2S_SA_MSB, 0)
    sa = rd32(mm, MM2S_SA)
    print("  [%s] MM2S_SA wr 0x%08X rd 0x%08X %s" % (label, SRC, sa, "OK" if sa == SRC else "FAIL"))
    return sa == SRC


def driver_style_start(mm, src, dst, length):
    """Xilinx xaxidma.c SimpleTransfer order: SA/DA, OR RS, LENGTH last."""
    wr32(mm, S2MM_DA, dst)
    wr32(mm, S2MM_DA_MSB, 0)
    wr32(mm, S2MM_CR, rd32(mm, S2MM_CR) | 0x1)
    wr32(mm, S2MM_LEN, length)

    wr32(mm, MM2S_SA, src)
    wr32(mm, MM2S_SA_MSB, 0)
    wr32(mm, MM2S_CR, rd32(mm, MM2S_CR) | 0x1)
    wr32(mm, MM2S_LEN, length)


def poll_ioc(mm, ms=2000):
    for i in range(ms // 4):
        sr_m, sr_s = rd32(mm, MM2S_SR), rd32(mm, S2MM_SR)
        if (sr_m & ERR_MASK) or (sr_s & ERR_MASK):
            return False, sr_m, sr_s, "ERR"
        if (sr_m & IOC) and (sr_s & IOC):
            return True, sr_m, sr_s, "IOC"
        time.sleep(0.004)
    return False, rd32(mm, MM2S_SR), rd32(mm, S2MM_SR), "TIMEOUT"


def main():
    print("=== board_dma_verify ===")
    try:
        with open("/lib/firmware/cifar10_accel.bit", "rb") as f:
            print("bit md5:", hashlib.md5(f.read()).hexdigest())
    except OSError:
        pass
    for p in ("/sys/class/fpga_manager/fpga0/state",):
        try:
            print("%s: %s" % (p, open(p).read().strip()))
        except OSError:
            pass

    if not test_gpio():
        print("VERDICT: GP0/GPIO failed — stop before DMA")
        return 2

    try:
        with open("/proc/iomem", "r", encoding="utf-8", errors="replace") as f:
            iomem = f.read()
        pl_hits = [ln for ln in iomem.splitlines() if "a0000000" in ln.lower() or "a0010000" in ln.lower()]
        if pl_hits:
            print("iomem PL:", "; ".join(pl_hits))
        else:
            print("iomem: no explicit 0x80040000/0x80090000 (fpga_manager overlay — devmem still OK if no DT node)")
    except OSError:
        pass

    pattern = bytes((i & 0xFF for i in range(16)))
    if not cma_rw(SRC, pattern):
        print("VERDICT: CMA @0x%08X R/W failed" % SRC)
        return 3
    print("CMA @0x%08X: R/W OK" % SRC)

    fd, mm = open_mm(DMA)
    print("\n--- Initial DMA ---")
    print("  MM2S DMACR=0x%08X DMASR=0x%08X" % (rd32(mm, MM2S_CR), rd32(mm, MM2S_SR)))
    print("  S2MM DMACR=0x%08X DMASR=0x%08X" % (rd32(mm, S2MM_CR), rd32(mm, S2MM_SR)))

    soft_reset(mm)
    print("\n--- SA write tests (after soft reset) ---")
    ok_rs1 = try_sa_write(mm, "RS=1 then SA", rs_before=True)
    soft_reset(mm)
    ok_drv = try_sa_write(mm, "SA then RS=1", rs_before=False)
    wr32(mm, MM2S_CR, rd32(mm, MM2S_CR) | 0x1)
    if not ok_rs1 and not ok_drv:
        mm.close()
        os.close(fd)
        print("\nVERDICT: MM2S_SA not writable — DMA lite / PL issue")
        return 4

    print("\n--- Loopback transfer (%d B, driver-style init) ---" % TEST_LEN)
    tx = bytes((i & 0xFF for i in range(TEST_LEN)))
    lib = ctypes.CDLL("libc.so.6")

    def flush_phys(phys, data):
        fdw = os.open("/dev/mem", os.O_RDWR | os.O_SYNC)
        mmw = mmap.mmap(fdw, len(data), mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE, offset=phys)
        mmw[:] = data
        ptr = ctypes.cast(ctypes.addressof(ctypes.c_char.from_buffer(mmw)), ctypes.c_void_p)
        lib.msync(ptr, len(data), 4)
        mmw.close()
        os.close(fdw)

    def read_phys(phys, n):
        fdr = os.open("/dev/mem", os.O_RDWR | os.O_SYNC)
        mmr = mmap.mmap(fdr, n, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE, offset=phys)
        ptr = ctypes.cast(ctypes.addressof(ctypes.c_char.from_buffer(mmr)), ctypes.c_void_p)
        lib.madvise(ptr, n, 4)
        data = bytes(mmr[:n])
        mmr.close()
        os.close(fdr)
        return data

    flush_phys(SRC, tx)
    flush_phys(DST, b"\x00" * TEST_LEN)

    soft_reset(mm)
    # Prime AXIS loopback FIFO (depth 16) — first transfer can slip by FIFO depth bytes.
    driver_style_start(mm, SRC, DST, TEST_LEN)
    poll_ioc(mm)
    soft_reset(mm)

    flush_phys(SRC, tx)
    flush_phys(DST, b"\x00" * TEST_LEN)
    soft_reset(mm)
    driver_style_start(mm, SRC, DST, TEST_LEN)
    print("  post-start SA=0x%08X LEN=0x%08X DA=0x%08X" % (
        rd32(mm, MM2S_SA), rd32(mm, MM2S_LEN), rd32(mm, S2MM_DA)))
    ok, sr_m, sr_s, reason = poll_ioc(mm)
    print("  poll: %s MM2S_SR=0x%08X S2MM_SR=0x%08X" % (reason, sr_m, sr_s))
    rx = read_phys(DST, TEST_LEN)
    mm.close()
    os.close(fd)

    if ok and rx == tx:
        print("\nVERDICT: DMA loopback OK")
        return 0
    if ok:
        print("\nVERDICT: DMA IOC but data mismatch (HP/cache)")
        return 5
    print("\nVERDICT: DMA registers OK but transfer incomplete (stream/M_AXI)")
    return 6


if __name__ == "__main__":
    sys.exit(main())
