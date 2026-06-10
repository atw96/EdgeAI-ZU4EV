#!/usr/bin/env python3
"""
EdgeAI-ZU4EV — FPGA inference benchmark (devmem + AXI-DMA).

Measures:
  - E2E latency (perf_counter, includes DMA transfer + HLS)
  - Top-1 accuracy on deploy/cifar10_bench.npz

Run on board (PetaLinux):
    python3 board_benchmark.py

Env:
    BENCH_NPZ   path to npz (default: cifar10_bench.npz in cwd)
    N_BENCH     latency repetitions (default 100)
    N_ACCURACY  accuracy images (default 100)
"""
import json
import mmap
import os
import struct
import sys
import time
import ctypes

import numpy as np

DMA = 0x80040000
SRC_PHYS = 0x66C00000
DST_PHYS = 0x66C02000
IN_BYTES = 6144
OUT_BYTES = 20
IOC = 0x1000

CLASS_NAMES = [
    'airplane', 'automobile', 'bird', 'cat', 'deer',
    'dog', 'frog', 'horse', 'ship', 'truck',
]

BENCH_NPZ = os.environ.get('BENCH_NPZ', 'cifar10_bench.npz')
N_BENCH = int(os.environ.get('N_BENCH', '100'))
N_ACCURACY = int(os.environ.get('N_ACCURACY', '100'))
OUT_JSON = os.environ.get('OUT_JSON', 'fpga_benchmark.json')


class DmaInfer:
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

    def inv_read(self, phys, n):
        mm, off = self._mmap(phys, n)
        ptr = ctypes.cast(
            ctypes.addressof(ctypes.c_char.from_buffer(mm)), ctypes.c_void_p)
        self._lib.madvise(ptr, n, 4)
        data = bytes(mm[off:off + n])
        mm.close()
        return data

    def soft_reset(self):
        self.wr(DMA + 0x00, self.rd(DMA + 0x00) | 0x4)
        self.wr(DMA + 0x30, self.rd(DMA + 0x30) | 0x4)
        for _ in range(500):
            if not (self.rd(DMA + 0x00) & 0x4) and not (self.rd(DMA + 0x30) & 0x4):
                return True
            time.sleep(0.002)
        return False

    def _clear_ioc(self):
        """Write-1-to-clear IOC sticky bits on both channels."""
        for sr in (DMA + 0x04, DMA + 0x34):
            val = self.rd(sr)
            if val & IOC:
                self.wr(sr, IOC)

    def _wait_ioc(self, timeout_s=5.0):
        deadline = time.perf_counter() + timeout_s
        while time.perf_counter() < deadline:
            s2mm = self.rd(DMA + 0x34)
            mm2s = self.rd(DMA + 0x04)
            if (s2mm & IOC) and (mm2s & IOC):
                return True
        return False

    def infer_once(self, payload, reset=True, time_dma=True):
        """
        Run one inference.

        time_dma=True: perf_counter from DMA start to IOC (excludes buffer prep).
        reset=True: include dma_soft_reset before each run.
        Returns (scores_float32[10], latency_ms or None).
        """
        assert len(payload) == IN_BYTES
        if reset:
            self.soft_reset()
        self._clear_ioc()
        self.flush_write(SRC_PHYS, payload)
        self.flush_write(DST_PHYS, b'\x00' * OUT_BYTES)

        t0 = time.perf_counter() if time_dma else None
        self.wr(DMA + 0x30, 0x1 | IOC)
        self.wr(DMA + 0x48, DST_PHYS)
        self.wr(DMA + 0x4C, 0)
        self.wr(DMA + 0x58, OUT_BYTES)
        self.wr(DMA + 0x00, 0x1 | IOC)
        self.wr(DMA + 0x18, SRC_PHYS)
        self.wr(DMA + 0x1C, 0)
        self.wr(DMA + 0x28, IN_BYTES)

        if not self._wait_ioc():
            return None, None

        t1 = time.perf_counter() if time_dma else None
        raw = self.inv_read(DST_PHYS, OUT_BYTES)
        scores = np.array(
            [struct.unpack_from('<h', raw, k * 2)[0] / 1024.0 for k in range(10)],
            dtype=np.float32,
        )
        lat_ms = (t1 - t0) * 1000.0 if time_dma else None
        return scores, lat_ms

    def infer_e2e(self, payload):
        """Full path: reset + buffer write + DMA + IOC."""
        t0 = time.perf_counter()
        scores, _ = self.infer_once(payload, reset=True, time_dma=False)
        if scores is None:
            return None, None
        t1 = time.perf_counter()
        return scores, (t1 - t0) * 1000.0


def load_bench_npz(path):
    if not os.path.isfile(path):
        print('[ERROR] Missing %s' % path)
        sys.exit(1)
    data = np.load(path, allow_pickle=True)
    payloads = list(data['payloads'])
    labels = data['labels'].astype(np.int32)
    return payloads, labels


def main():
    print('=' * 60)
    print('  EdgeAI-ZU4EV: FPGA Benchmark (devmem + AXI-DMA)')
    print('=' * 60)

    payloads, labels = load_bench_npz(BENCH_NPZ)
    n_acc = min(N_ACCURACY, len(payloads))
    n_bench = min(N_BENCH, len(payloads))
    print('  Dataset : %s (%d samples)' % (BENCH_NPZ, len(payloads)))

    dma = DmaInfer()
    try:
        print('\nWarm-up...')
        scores, _ = dma.infer_once(payloads[0], reset=True, time_dma=False)
        if scores is None:
            print('[ERROR] Warm-up inference failed (DMA timeout)')
            return 1
        print('  Warm-up OK')

        print('\nLatency benchmark (%d runs, sample 0, DMA-start→IOC)...' % n_bench)
        latencies = []
        for i in range(n_bench):
            _, lat = dma.infer_once(
                payloads[0], reset=True, time_dma=True,
            )
            if lat is None:
                print('[ERROR] Timeout at run %d' % i)
                return 1
            latencies.append(lat)
        lat_arr = np.array(latencies[1:] if len(latencies) > 1 else latencies)

        print('\nE2E benchmark (10 runs, reset+prep+DMA+IOC)...')
        e2e = []
        for i in range(10):
            _, lat = dma.infer_e2e(payloads[0])
            if lat is None:
                print('[ERROR] E2E timeout at run %d' % i)
                return 1
            e2e.append(lat)
        e2e_arr = np.array(e2e[1:] if len(e2e) > 1 else e2e)

        print('\nAccuracy benchmark (%d images)...' % n_acc)
        preds = []
        for i in range(n_acc):
            scores, _ = dma.infer_once(payloads[i], reset=False, time_dma=False)
            if scores is None:
                print('[ERROR] Accuracy run %d timeout' % i)
                return 1
            preds.append(int(np.argmax(scores)))
        preds = np.array(preds, dtype=np.int32)
        true = labels[:n_acc]
        accuracy = float(np.mean(preds == true) * 100.0)

        result = {
            'platform': 'ZU4EV FPGA (HLS + AXI-DMA devmem)',
            'bench_npz': BENCH_NPZ,
            'n_bench': int(n_bench),
            'n_accuracy': int(n_acc),
            'dma_latency_ms': {
                'mean': round(float(lat_arr.mean()), 4),
                'std': round(float(lat_arr.std()), 4),
                'min': round(float(lat_arr.min()), 4),
                'max': round(float(lat_arr.max()), 4),
            },
            'e2e_latency_ms': {
                'mean': round(float(e2e_arr.mean()), 4),
                'std': round(float(e2e_arr.std()), 4),
                'min': round(float(e2e_arr.min()), 4),
                'max': round(float(e2e_arr.max()), 4),
            },
            'accuracy_top1': round(accuracy, 2),
            'note_dma': 'perf_counter MM2S/S2MM start to dual IOC; reset+clear IOC each run',
            'hls_ip_latency_ms_csynth': 13.370,
            'note_ip': 'Pure HLS IP latency from myproject_axi_csynth.rpt (see hls_ip_latency.json)',
            'note_e2e': 'perf_counter includes soft_reset, buffer flush, DMA, busy-wait IOC',
        }

        print('\n--- Results ---')
        print('  DMA latency  : %.3f ± %.3f ms (min %.3f)' % (
            result['dma_latency_ms']['mean'],
            result['dma_latency_ms']['std'],
            result['dma_latency_ms']['min'],
        ))
        print('  E2E latency  : %.3f ± %.3f ms (min %.3f)' % (
            result['e2e_latency_ms']['mean'],
            result['e2e_latency_ms']['std'],
            result['e2e_latency_ms']['min'],
        ))
        print('  Top-1 Acc    : %.2f%% (%d images)' % (accuracy, n_acc))

        with open(OUT_JSON, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2)
        print('\nSaved: %s' % OUT_JSON)
        return 0
    finally:
        dma.close()


if __name__ == '__main__':
    sys.exit(main())
