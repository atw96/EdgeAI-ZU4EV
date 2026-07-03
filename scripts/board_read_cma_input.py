#!/usr/bin/env python3
"""On board: stage MM2S payload to CMA and read back for host compare (no partial DMA)."""
import json
import os
import sys

from dma_infer_common import DevMemDma, IN_BYTES, SRC_PHYS, require_pl_operating


def main():
    import numpy as np

    npz = os.environ.get('BENCH_NPZ', 'cifar10_bench.npz')
    idx = int(os.environ.get('SAMPLE_IDX', '0'))
    n_read = int(os.environ.get('CMA_READ_BYTES', str(IN_BYTES)))
    run_dma = os.environ.get('RUN_DMA_AFTER_READ', '0') == '1'

    if not os.path.isabs(npz):
        npz = os.path.join(os.path.dirname(os.path.abspath(__file__)), npz)
    data = np.load(npz, allow_pickle=True)
    payload = bytes(data['payloads'][idx])
    if len(payload) != IN_BYTES:
        print(json.dumps({'ok': False, 'error': 'payload len %d != IN_BYTES %d' % (len(payload), IN_BYTES)}))
        return 1

    skip_dma = os.environ.get('SKIP_DMA_RESET', '1') == '1'
    try:
        require_pl_operating()
    except RuntimeError as exc:
        print(json.dumps({'ok': False, 'error': str(exc)}))
        return 2

    dma = DevMemDma()
    try:
        if not skip_dma:
            dma.soft_reset()
            dma.clear_ioc()
        dma.flush_write(SRC_PHYS, payload)
        staged = dma.inv_read(SRC_PHYS, n_read, after_dma=False)

        out = {
            'ok': True,
            'sample_idx': idx,
            'skip_dma_reset': skip_dma,
            'src_phys': hex(SRC_PHYS),
            'in_bytes': IN_BYTES,
            'read_bytes': n_read,
            'payload_hex_head': payload[:64].hex(),
            'staged_hex_head': staged[:64].hex(),
            'payload_match_staged': payload[:n_read] == staged[:n_read],
            'mismatch_count': sum(
                1 for i in range(min(len(payload), len(staged)))
                if payload[i] != staged[i]
            ),
        }
        if run_dma and not skip_dma:
            from dma_infer_common import DST_PHYS, OUT_BYTES
            dma.flush_write(DST_PHYS, b'\x00' * OUT_BYTES)
            dma.start_transfer()
            ok, mm2s, s2mm, st = dma.wait_ioc()
            out['dma'] = {
                'ok': ok, 'status': st,
                'mm2s_sr': hex(mm2s), 's2mm_sr': hex(s2mm),
            }
        print(json.dumps(out))
        return 0
    finally:
        dma.close()


if __name__ == '__main__':
    sys.exit(main())
