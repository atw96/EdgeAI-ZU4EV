#!/usr/bin/env python3
"""AA prefill 96 bytes under serial GAP env; print word stats."""
import os, struct, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dma_infer_common import DevMemDma, DST_PHYS

def main():
    npz = os.environ.get("BENCH_NPZ", "cifar10_bench.npz")
    data = np.load(npz, allow_pickle=True)
    payload = bytes(data["payloads"][0])
    prefill = int(os.environ.get("PREFILL_BYTES", "96"))
    dma = DevMemDma()
    try:
        dma.soft_reset()
        dma.clear_ioc()
        dma.flush_write(0x66C00000, payload)
        dma.flush_write(DST_PHYS, b"\xaa" * prefill)
        dma.start_transfer()
        ok, mm2s, s2mm, st = dma.wait_ioc()
        raw = dma.inv_read(DST_PHYS, prefill, after_dma=True)
        words = [struct.unpack_from("<I", raw, w * 4)[0] for w in range(prefill // 4)]
        print("=== board_aa_serial96 ok=%s status=%s ===" % (ok, st))
        print("words[0:12] hex:", [hex(w) for w in words[:12]])
        zero_idx = [i for i, w in enumerate(words) if w == 0]
        aa_idx = [i for i, w in enumerate(words) if w == 0xAAAAAAAA]
        other_idx = [i for i, w in enumerate(words) if w not in (0, 0xAAAAAAAA)]
        print("zero word indices:", zero_idx)
        print("0xAAAAAAAA indices:", aa_idx)
        print("other indices:", other_idx)
        print("nonzero count:", sum(1 for w in words if w != 0))
    finally:
        dma.close()
    return 0

if __name__ == "__main__":
    sys.exit(main())