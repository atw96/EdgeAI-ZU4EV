import hashlib
import os
import numpy as np
from dma_infer_common import DST_PHYS, OUT_BYTES, SRC_PHYS, DevMemDma, require_pl_operating

require_pl_operating()
kat = np.load(os.environ["KAT_NPZ"])
raw_in = kat["payloads"][0].tobytes()
print("payload", len(raw_in), hashlib.md5(raw_in).hexdigest(), list(raw_in[:16]))
g = np.load(os.environ["KAT_GOLDEN"])["gap"]
golden = np.rint(np.asarray(g, dtype=np.float64) * 1024.0).astype(np.int32)[0]
dma = DevMemDma()
try:
    for n in range(3):
        if not dma.soft_reset():
            raise SystemExit(3)
        dma.clear_ioc()
        dma.flush_write(DST_PHYS, b"\xAA" * OUT_BYTES)
        dma.flush_write(SRC_PHYS, raw_in)
        landed = dma.inv_read(SRC_PHYS, 6144, after_dma=False)
        print("landed_md5", hashlib.md5(landed).hexdigest(), "match", landed == raw_in)
        dma.start_transfer()
        ok, _, _, why = dma.wait_ioc()
        raw = dma.inv_read(DST_PHYS, OUT_BYTES, after_dma=True)
        gap = np.asarray(dma.decode_gap_features(raw), dtype=np.float64)
        lsb = np.rint(gap * 1024.0).astype(np.int32)
        print("run", n, "dma", ok, why, "max", int(np.abs(lsb - golden).max()))
        print("lsb", lsb.tolist())
finally:
    dma.close()
