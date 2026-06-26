#!/usr/bin/env python3
"""CIFAR-10 FPGA inference demo (devmem + AXI-DMA). Run on board."""
import os
import sys
import time

import numpy as np

from dma_infer_common import DevMemDma, IN_BYTES, DST_PHYS, OUT_BYTES

CLASSES = [
    'airplane', 'automobile', 'bird', 'cat', 'deer',
    'dog', 'frog', 'horse', 'ship', 'truck',
]

BENCH_NPZ = os.environ.get('BENCH_NPZ', 'cifar10_bench.npz')
N_DEMO = int(os.environ.get('N_DEMO', '3'))


def load_payloads():
    npz = BENCH_NPZ
    if not os.path.isabs(npz):
        here = os.path.dirname(os.path.abspath(__file__))
        npz = os.path.join(here, npz)
    if not os.path.isfile(npz):
        print('[ERROR] Missing %s — copy deploy/cifar10_bench.npz to board' % npz)
        sys.exit(1)
    data = np.load(npz, allow_pickle=True)
    payloads = list(data['payloads'])
    labels = data['labels'].astype(np.int32)
    return payloads, labels


def run_inference(dma, payload, label_name, quiet=False):
    assert len(payload) == IN_BYTES
    if not quiet:
        print('\n--- Running inference: expected=%s ---' % label_name)

    dma.soft_reset()
    dma.clear_ioc()
    dma.flush_write(0x66C00000, payload)
    dma.flush_write(DST_PHYS, b'\x00' * OUT_BYTES)

    t0 = time.perf_counter()
    dma.start_transfer()
    ok, mm2s, s2mm, status = dma.wait_ioc()
    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    if not ok:
        if not quiet:
            print('  FAILED: %s  MM2S_SR=0x%08X  S2MM_SR=0x%08X' % (status, mm2s, s2mm))
        return False

    scores = dma.decode_scores()
    pred = int(np.argmax(scores))
    if not quiet:
        print('  Done in %.1fms  MM2S_SR=0x%08X  S2MM_SR=0x%08X' % (elapsed_ms, mm2s, s2mm))
        print('  Scores: %s' % [round(s, 3) for s in scores])
        print('  Prediction: %s (class %d)' % (CLASSES[pred], pred))
        print('  Correct:    %s' % (CLASSES[pred] == label_name))
    return CLASSES[pred] == label_name


def check_pl_state():
    """Warn if fpga_manager is not operating (inference needs loaded bit)."""
    state_path = '/sys/class/fpga_manager/fpga0/state'
    try:
        state = open(state_path).read().strip()
        if state != 'operating':
            print('[WARN] fpga_manager state=%s — run board_load_only.sh first' % state)
    except OSError:
        pass


def main():
    check_pl_state()
    payloads, labels = load_payloads()
    n = min(N_DEMO, len(payloads))
    dma = DevMemDma()
    try:
        print('--- Warm-up (prime HLS/DMA pipeline, discard result) ---')
        print('  OUT_BYTES=%d OUT_LAYOUT=%s' % (
            OUT_BYTES, os.environ.get('OUT_LAYOUT', 'int16')))
        dma.soft_reset()
        dma.clear_ioc()
        dma.flush_write(0x66C00000, payloads[0])
        dma.flush_write(DST_PHYS, b'\x00' * OUT_BYTES)
        dma.start_transfer()
        ok, _, _, status = dma.wait_ioc()
        if not ok:
            print('  Warm-up FAILED: %s' % status)
            return 1
        print('  Warm-up OK')

        ok_count = 0
        for i in range(n):
            name = CLASSES[int(labels[i])]
            if run_inference(dma, payloads[i], name):
                ok_count += 1

        print('\nDemo summary: %d/%d correct' % (ok_count, n))
        return 0 if ok_count == n else 1
    finally:
        dma.close()


if __name__ == '__main__':
    sys.exit(main())
