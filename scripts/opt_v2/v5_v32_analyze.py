#!/usr/bin/env python3
"""Interpret the V3.2 raw capture: input readback, history, high 16 bits."""
import hashlib
import json
from pathlib import Path

import numpy as np

SYN = (Path(__file__).resolve().parents[2] / 'results/opt_v2/v5_synth')
rawp = np.load(SYN / "v32_raw.npz", allow_pickle=True)
tags = [str(t) for t in rawp["tags"]]
src = rawp["src"]
raw = rawp["raw"]
frames = np.load(SYN / "v32_frames.npz")

def lsb(buf):
    return np.frombuffer(buf.tobytes(), dtype="<i2")[0::2].copy()

def hi(buf):
    return np.frombuffer(buf.tobytes(), dtype="<i2")[1::2].copy()

src_ok = {}
for name in frames.files:
    payload = np.asarray(frames[name])
    src_ok[name] = {
        "host_md5": hashlib.md5(payload.tobytes()).hexdigest(),
        "nbytes": int(payload.size),
    }

black_raw = []
for i, tag in enumerate(tags):
    if "black" in tag or tag.startswith("reset_black") or tag.startswith("after_"):
        black_raw.append((tag, raw[i].tobytes()))

# all tags whose output should be the black frame
black_tags = [t for t in tags if t.startswith("reset_black") or t.startswith("after_") or t.startswith("pre_black")]
uniq = {}
for i, tag in enumerate(tags):
    if tag in black_tags or tag.startswith("after_") or tag.startswith("reset_black") or tag.startswith("pre_black"):
        uniq.setdefault(raw[i].tobytes(), []).append(tag)

rows = []
for i, tag in enumerate(tags):
    lo = lsb(raw[i])
    high = hi(raw[i])
    rows.append({
        "tag": tag,
        "src_md5": hashlib.md5(src[i].tobytes()).hexdigest(),
        "src_first64": src[i][:64].tobytes().hex(),
        "lo": lo.tolist(),
        "hi": high.tolist(),
        "hi_nonzero": int(np.count_nonzero(high)),
        "aa_hi": int(sum(1 for k in range(24) if raw[i, k * 4 + 2] == 0xAA and raw[i, k * 4 + 3] == 0xAA)),
    })

black_outputs = [r["lo"] for r in rows if r["tag"].startswith(("reset_black", "after_", "pre_black"))]
same_black = all(x == black_outputs[0] for x in black_outputs)

# host payload vs readback for the first black and gray52
def expect(name):
    return hashlib.md5(np.asarray(frames[name]).tobytes()).hexdigest()

report = {
    "n": len(tags),
    "host_md5": {k: expect(k) for k in frames.files},
    "black_output_identical_across_history": bool(same_black),
    "n_distinct_black_raw": len({raw[i].tobytes() for i, t in enumerate(tags) if t.startswith(("reset_black", "after_", "pre_black"))}),
    "frames": rows,
}
(SYN / "v5_v32_ab.json").write_text(json.dumps(report))
print("black history identical", same_black, "distinct", report["n_distinct_black_raw"])
print("host", report["host_md5"])
for r in rows:
    if r["tag"] in ("reset_black_0", "after_nat_0", "after_white_0", "after_black_0", "gray51", "gray52", "pre_white_0", "pre_nat_0"):
        match = "src_ok" if r["src_md5"] == report["host_md5"].get(
            {"reset_black_0": "black", "after_nat_0": "black", "after_white_0": "black",
             "after_black_0": "black", "gray51": "gray51", "gray52": "gray52",
             "pre_white_0": "white", "pre_nat_0": "natural"}[r["tag"]]
        ) else "SRC_MISMATCH"
        print(r["tag"], match, "hi_nonzero", r["hi_nonzero"], "aa", r["aa_hi"])
        print("  lo", r["lo"])
        print("  hi", r["hi"])
