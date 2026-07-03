"""Shared AXI-DMA + devmem inference helpers for board scripts."""
import mmap
import os
import struct
import time
import ctypes

from slot32_layout import (
    decode_board_s2mm_raw,
    decode_serial32_raw,
    decode_slot32_raw,
    serial32_out_bytes,
    slot32_out_bytes,
)

DMA = 0x80040000
SRC_PHYS = 0x66C00000
DST_PHYS = 0x66C02000
IN_BYTES = 6144
OUT_DIM = int(os.environ.get('OUT_DIM', '10'))
OUT_LAYOUT = os.environ.get('OUT_LAYOUT', 'int16')
OUTPUT_PACK_MODE = os.environ.get('OUTPUT_PACK_MODE', 'slot').lower()
if OUT_LAYOUT in ('slot32', 'gap_ps'):
    if OUTPUT_PACK_MODE == 'serial':
        _default_out_bytes = serial32_out_bytes(OUT_DIM)
    else:
        _default_out_bytes = slot32_out_bytes(OUT_DIM)
else:
    _default_out_bytes = 40 if OUT_LAYOUT == 'serial32' else 20
OUT_BYTES = int(os.environ.get('OUT_BYTES', str(_default_out_bytes)))
BOARD_S2MM_SLOT_TIMING = os.environ.get('BOARD_S2MM_SLOT_TIMING', '0') != '0'


def decode_dram_hole_pairs_raw(raw, out_scale, n_outputs=None):
    """S2MM 32-bit DMA -> 64-bit HP sparse layout: 2 data dwords + 2 hole dwords."""
    if n_outputs is None:
        n_outputs = int(os.environ.get('OUT_DIM', '10'))
    scale = float(out_scale)
    scores = [0.0] * n_outputs
    word = 0
    li = 0
    while li < n_outputs and (word * 4) < len(raw):
        scores[li] = struct.unpack_from('<h', raw, word * 4)[0] / scale
        li += 1
        word += 1
        if li < n_outputs and li % 2 == 0:
            word += 2
    return scores


def dram_has_hole_pair_layout(raw, n_outputs=None):
    if n_outputs is None:
        n_outputs = int(os.environ.get('OUT_DIM', '10'))
    n_words = len(raw) // 4
    if n_words < 4:
        return False
    holes = 0
    pairs = 0
    word = 2
    while word + 1 < min(n_words, n_outputs):
        pairs += 1
        if struct.unpack_from('<I', raw, word * 4)[0] == 0 and \
                struct.unpack_from('<I', raw, (word + 1) * 4)[0] == 0:
            holes += 1
        word += 4
    return pairs > 0 and holes >= pairs // 2


def decode_gap_raw(raw, out_scale=None, n_outputs=None):
    if n_outputs is None:
        n_outputs = OUT_DIM
    if out_scale is None:
        out_scale = int(os.environ.get('OUT_FIXED_SCALE', '1024'))
    if OUTPUT_PACK_MODE == 'serial':
        if BOARD_S2MM_SLOT_TIMING:
            return decode_board_s2mm_raw(raw, out_scale, n_outputs)
        if dram_has_hole_pair_layout(raw, n_outputs):
            return decode_dram_hole_pairs_raw(raw, out_scale, n_outputs)
        return decode_serial32_raw(raw, out_scale, n_outputs)
    return decode_slot32_raw(raw, out_scale, n_outputs)

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


_PAGE_SIZE = 0x1000
_PAGE_MASK = _PAGE_SIZE - 1


def require_pl_operating(exit_on_fail=True):
    """Refuse devmem/DMA if fpga_manager is not operating (prevents AXI hang / SSH loss)."""
    state_path = os.environ.get(
        'FPGA_STATE_PATH', '/sys/class/fpga_manager/fpga0/state')
    try:
        with open(state_path, 'r', encoding='utf-8') as fh:
            state = fh.read().strip()
    except OSError as exc:
        msg = 'cannot read %s: %s' % (state_path, exc)
        if exit_on_fail:
            raise RuntimeError(msg)
        return False, msg
    required = os.environ.get('REQUIRED_PL_STATE', 'operating')
    if state != required:
        msg = (
            'PL not loaded (fpga0 state=%r, need %r). '
            'Run: FORCE_PL_RELOAD=1 sh board_load_only.sh BEFORE any /dev/mem or DMA script.'
            % (state, required)
        )
        if exit_on_fail:
            raise RuntimeError(msg)
        return False, msg
    return True, state


class DevMemDma:
    def __init__(self):
        self._fd = os.open('/dev/mem', os.O_RDWR | os.O_SYNC)
        self._lib = ctypes.CDLL('libc.so.6')
        self._page_maps = {}

    def close(self):
        for mm in self._page_maps.values():
            mm.close()
        self._page_maps.clear()
        os.close(self._fd)

    def _map_page(self, addr):
        page = addr & ~_PAGE_MASK
        if page not in self._page_maps:
            mm = mmap.mmap(
                self._fd, _PAGE_SIZE, mmap.MAP_SHARED,
                mmap.PROT_READ | mmap.PROT_WRITE, offset=page,
            )
            self._page_maps[page] = mm
        return self._page_maps[page], addr & _PAGE_MASK

    def wr(self, addr, val):
        mm, off = self._map_page(addr)
        mm[off:off + 4] = struct.pack('<I', val)

    def rd(self, addr):
        mm, off = self._map_page(addr)
        return struct.unpack('<I', mm[off:off + 4])[0]

    def flush_write(self, phys, data):
        pos = 0
        length = len(data)
        while pos < length:
            addr = phys + pos
            mm, off = self._map_page(addr)
            chunk = min(length - pos, _PAGE_SIZE - off)
            mm[off:off + chunk] = data[pos:pos + chunk]
            ptr = ctypes.cast(
                ctypes.addressof(ctypes.c_char.from_buffer(mm)), ctypes.c_void_p)
            self._lib.msync(ptr.value + off, chunk, _MS_SYNC)
            pos += chunk

    def inv_read(self, phys, n, after_dma=False):
        """Read physical memory. Use after_dma=True after S2MM to drop stale cache lines."""
        parts = []
        pos = 0
        while pos < n:
            addr = phys + pos
            mm, off = self._map_page(addr)
            chunk = min(n - pos, _PAGE_SIZE - off)
            ptr = ctypes.cast(
                ctypes.addressof(ctypes.c_char.from_buffer(mm)), ctypes.c_void_p)
            if after_dma:
                self._lib.msync(ptr.value + off, chunk, _MS_INVALIDATE | _MS_SYNC)
            else:
                self._lib.madvise(ptr.value + off, chunk, 4)
            parts.append(bytes(mm[off:off + chunk]))
            pos += chunk
        return b''.join(parts)

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

    def wait_ioc(self, timeout_s=None):
        if timeout_s is None:
            timeout_s = float(os.environ.get('DMA_IOC_TIMEOUT_S', '5.0'))
        poll_sleep = float(os.environ.get('DMA_POLL_SLEEP_S', '0.0005'))
        deadline = time.perf_counter() + timeout_s
        while time.perf_counter() < deadline:
            time.sleep(poll_sleep)
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
            out_scale = int(os.environ.get('OUT_FIXED_SCALE', '1024'))
        return decode_gap_raw(raw, out_scale, OUT_DIM)

    def decode_scores(self, raw=None, out_scale=None):
        if raw is None:
            raw = self.inv_read(DST_PHYS, OUT_BYTES, after_dma=True)
        if out_scale is None:
            out_scale = int(os.environ.get('OUT_FIXED_SCALE', '1024'))
        if OUT_LAYOUT == 'gap_ps':
            gap = self.decode_gap_features(raw, out_scale)
            return apply_ps_dense(gap)
        if OUT_LAYOUT == 'slot32':
            return decode_gap_raw(raw, out_scale, OUT_DIM)
        if OUT_LAYOUT == 'serial32':
            return [
                struct.unpack_from('<h', raw, k * 4)[0] / float(out_scale)
                for k in range(10)
            ]
        return [
            struct.unpack_from('<h', raw, k * 2)[0] / float(out_scale)
            for k in range(10)
        ]
