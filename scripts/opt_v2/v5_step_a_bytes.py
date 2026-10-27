#!/usr/bin/env python3
"""V3.2 step a, host side: packed DMA bytes vs the csim input text.

Both were built from the same int16 quantization. This checks the file pair
that the board and csim actually consumed. It does not touch the live HLS tree.
"""
import hashlib
import json
from pathlib import Path

import numpy as np

SYN = (Path(__file__).resolve().parents[2] / 'results/opt_v2/v5_synth')
pack = np.load(SYN / "synth_packed.npz")
payloads = pack["payloads"]
names = pack["names"]
n = len(payloads)
text = (SYN / "tb_input_features.dat").read_text().splitlines()
if len(text) != n:
    raise SystemExit(f"dat lines {len(text)} != payloads {n}")

bad = []
for i in range(n):
    vals = np.array([float(x) for x in text[i].split()], dtype=np.float64)
    recon = np.rint(vals * 1024.0).astype(np.int16).tobytes()
    sent = payloads[i].tobytes()
    if sent != recon:
        bad.append(int(i))
        if len(bad) >= 8:
            break

head = payloads[0][:64]
digest = hashlib.md5(payloads.tobytes()).hexdigest()
out = {
    "n": int(n),
    "payload_md5": digest,
    "n_mismatch_checked": int(n if not bad else min(n, bad[-1] + 1)),
    "n_byte_mismatch": len(bad),
    "mismatch_index_prefix": bad,
    "frame0_first64_hex": bytes(head).hex(),
    "frame0_checksum32": int(np.frombuffer(payloads[0].tobytes(), dtype=np.uint8).sum()),
}
lat = np.load(SYN / "board_lat_synth.npy")
out["board_latency_ms"] = {
    "n": int(lat.shape[0]),
    "median": float(np.median(lat)),
    "p99": float(np.quantile(lat, 0.99)),
    "min": float(lat.min()),
    "max": float(lat.max()),
}
(SYN / "v5_step_a_host.json").write_text(json.dumps(out, indent=1))
print(json.dumps(out, indent=1))
