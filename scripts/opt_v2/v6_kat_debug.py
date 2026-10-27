#!/usr/bin/env python3
import os
import numpy as np
from dma_infer_common import DST_PHYS, OUT_BYTES, SRC_PHYS, DevMemDma, require_pl_operating

require_pl_operating()
kat = np.load(os.environ["KAT_NPZ"])
g = np.load(os.environ["KAT_GOLDEN"])["gap"]
print("gap dtype", g.dtype, "shape", g.shape)
if g.dtype.kind == "f":
    golden = np.rint(g.astype(np.float64) * 1024.0).astype(np.int32)
else:
    golden = g.astype(np.int32)
print("golden0", golden[0].tolist())
dma = DevMemDma()
try:
    payload = kat["payloads"][0].tobytes()
    if not dma.soft_reset():
        raise SystemExit(3)
    dma.clear_ioc()
    dma.flush_write(DST_PHYS, b"\xAA" * OUT_BYTES)
    dma.flush_write(SRC_PHYS, payload)
    dma.start_transfer()
    ok, _, _, why = dma.wait_ioc()
    print("dma", ok, why)
    raw = dma.inv_read(DST_PHYS, OUT_BYTES, after_dma=True)
    gap = np.asarray(dma.decode_gap_features(raw), dtype=np.float64)
    lsb = np.rint(gap * 1024.0).astype(np.int32)
    print("board0", lsb.tolist())
    print("max", int(np.abs(lsb - golden[0]).max()))
finally:
    dma.close()
