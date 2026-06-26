"""Shared AXI-DMA + devmem inference helpers for board scripts."""
import mmap
import os
import struct
import time
import ctypes

from slot32_layout import decode_slot32_raw, slot32_out_bytes

DMA = 0x80040000
SRC_PHYS = 0x66C00000
DST_PHYS = 0x66C02000
IN_BYTES = 6144
OUT_DIM = int(os.environ.get('OUT_DIM', '10'))
OUT_LAYOUT = os.environ.get('OUT_LAYOUT', 'int16')
_default_out_bytes = slot32_out_bytes(OUT_DIM) if OUT_LAYOUT in (
    'slot32', 'gap_ps',
) else (40 if OUT_LAYOUT == 'serial32' else 20)
OUT_BYTES = int(os.environ.get('OUT_BYTES', str(_default_out_bytes)))
IOC = 0x1000
ERR_MASK = 0x770

MM2S_CR, MM2S_SR = 0x00, 0x04
MM2S_SA, MM2S_SA_MSB, MM2S_LEN = 0x18, 0x1C, 0x28
S2MM_CR, S2MM_SR = 0x30, 0x34
S2MM_DA, S2MM_DA_MSB, S2MM_LEN = 0x48, 0x4C, 0x58

# Linux msync(2): invalidate CPU cache after PL DMA wrote to DRAM
_MS_INVALIDATE = 2
_MS_SYNC = 4

_DENSE_CACHE = None


def load_dense_head():
    global _DENSE_CACHE
    if _DENSE_CACHE is not None:
        return _DENSE_CACHE
    import numpy as np

    path = os.environ.get('DENSE_NPZ', 'dense_head.npz')
    if not os.path.isabs(path):
        here = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(here, path)
        if not os.path.isfile(path):
            path = os.path.join(here, 'deploy', 'dense_head.npz')
    if not os.path.isfile(path):
        raise FileNotFoundError('dense weights missing: %s' % path)
    data = np.load(path)
    _DENSE_CACHE = (data['weight'], data['bias'])
    return _DENSE_CACHE


def apply_ps_dense(gap_features):
    import numpy as np

    w, b = load_dense_head()
    x = np.asarray(gap_features, dtype=np.float32)
    return (x @ w + b).tolist()


class DevMemDma:
    def __init__(self):
        self._fd = os.open('/dev/mem', os.O_RDWR | os.O_SYNC)
        self._lib = ctypes.CDLL('libc.so.6')

    def close(self):
        os.close(self._fd)

    def _mmap(self, addr, size):
        page = addr & ~0xFFF
        span = (size + 0xFFF) & ~0xFFF
        mm = mmap.mmap(
            self._fd, span, mmap.MAP_SHARED,
            mmap.PROT_READ | mmap.PROT_WRITE, offset=page,
        )
        return mm, addr & 0xFFF

    def wr(self, addr, val):
        mm, off = self._mmap(addr, 4)
        mm[off:off + 4] = struct.pack('<I', val)
        mm.close()

    def rd(self, addr):
        mm, off = self._mmap(addr, 4)
        val = struct.unpack('<I', mm[off:off + 4])[0]
        mm.close()
        return val

    def flush_write(self, phys, data):
        mm, off = self._mmap(phys, len(data))
        mm[off:off + len(data)] = data
        ptr = ctypes.cast(
            ctypes.addressof(ctypes.c_char.from_buffer(mm)), ctypes.c_void_p)
        self._lib.msync(ptr, len(data), 4)
        mm.close()

    def inv_read(self, phys, n, after_dma=False):
        """Read physical memory. Use after_dma=True after S2MM to drop stale cache lines."""
        mm, off = self._mmap(phys, n)
        ptr = ctypes.cast(
            ctypes.addressof(ctypes.c_char.from_buffer(mm)), ctypes.c_void_p)
        if after_dma:
            self._lib.msync(ptr, n, _MS_INVALIDATE | _MS_SYNC)
        else:
            self._lib.madvise(ptr, n, 4)
        data = bytes(mm[off:off + n])
        mm.close()
        return data

    def soft_reset(self):
        self.wr(DMA + MM2S_CR, self.rd(DMA + MM2S_CR) | 0x4)
        self.wr(DMA + S2MM_CR, self.rd(DMA + S2MM_CR) | 0x4)
        for _ in range(500):
            if not (self.rd(DMA + MM2S_CR) & 0x4) and not (self.rd(DMA + S2MM_CR) & 0x4):
                return True
            time.sleep(0.002)
        return False

    def clear_ioc(self):
        for sr in (DMA + MM2S_SR, DMA + S2MM_SR):
            val = self.rd(sr)
            if val & IOC:
                self.wr(sr, IOC)

    def start_transfer(self):
        """Xilinx xaxidma SimpleTransfer order: DA/SA, RS, LENGTH (S2MM then MM2S)."""
        self.wr(DMA + S2MM_DA, DST_PHYS)
        self.wr(DMA + S2MM_DA_MSB, 0)
        self.wr(DMA + S2MM_CR, self.rd(DMA + S2MM_CR) | 0x1)
        self.wr(DMA + S2MM_LEN, OUT_BYTES)

        self.wr(DMA + MM2S_SA, SRC_PHYS)
        self.wr(DMA + MM2S_SA_MSB, 0)
        self.wr(DMA + MM2S_CR, self.rd(DMA + MM2S_CR) | 0x1)
        self.wr(DMA + MM2S_LEN, IN_BYTES)

    def wait_ioc(self, timeout_s=5.0):
        deadline = time.perf_counter() + timeout_s
        while time.perf_counter() < deadline:
            s2mm = self.rd(DMA + S2MM_SR)
            mm2s = self.rd(DMA + MM2S_SR)
            if (s2mm & ERR_MASK) or (mm2s & ERR_MASK):
                return False, mm2s, s2mm, 'ERR'
            if (s2mm & IOC) and (mm2s & IOC):
                return True, mm2s, s2mm, 'IOC'
        return False, self.rd(DMA + MM2S_SR), self.rd(DMA + S2MM_SR), 'TIMEOUT'

    @staticmethod
    def decode_slot32_raw(raw, out_scale, n_outputs=None):
        return decode_slot32_raw(raw, out_scale, n_outputs)

    def decode_gap_features(self, raw=None, out_scale=None):
        if raw is None:
            raw = self.inv_read(DST_PHYS, OUT_BYTES, after_dma=True)
        if out_scale is None:
            out_scale = int(os.environ.get('OUT_FIXED_SCALE', '256'))
        return decode_slot32_raw(raw, out_scale, OUT_DIM)

    def decode_scores(self, raw=None, out_scale=None):
        if raw is None:
            raw = self.inv_read(DST_PHYS, OUT_BYTES, after_dma=True)
        if out_scale is None:
            out_scale = int(os.environ.get('OUT_FIXED_SCALE', '256'))
        if OUT_LAYOUT == 'gap_ps':
            gap = self.decode_gap_features(raw, out_scale)
            return apply_ps_dense(gap)
        if OUT_LAYOUT == 'slot32':
            return decode_slot32_raw(raw, out_scale, OUT_DIM)
        if OUT_LAYOUT == 'serial32':
            return [
                struct.unpack_from('<h', raw, k * 4)[0] / float(out_scale)
                for k in range(10)
            ]
        return [
            struct.unpack_from('<h', raw, k * 2)[0] / float(out_scale)
            for k in range(10)
        ]
