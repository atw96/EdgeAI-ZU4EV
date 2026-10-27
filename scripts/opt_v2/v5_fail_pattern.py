#!/usr/bin/env python3
"""Describe the 83 board!=csim frames without changing the design."""
import json
from pathlib import Path

import numpy as np

SYN = (Path(__file__).resolve().parents[2] / 'results/opt_v2/v5_synth')
suite = np.load(SYN / "synth_suite.npz", allow_pickle=True)
names = suite["names"]
cats = suite["cats"]
images = suite["images"]
board = np.load(SYN / "board_gap_synth.npy").astype(np.int32)
csim = np.rint(np.load(SYN / "csim_gap.npy").astype(np.float64) * 1024.0).astype(np.int32)
per = np.abs(board - csim).max(axis=1)
fail = np.where(per > 0)[0]

rows = []
for i in fail:
    b = board[i]
    c = csim[i]
    bnz = [int(k) for k in np.where(b != 0)[0]]
    cnz = [int(k) for k in np.where(c != 0)[0]]
    img = images[i]
    rows.append({
        "i": int(i),
        "name": str(names[i]),
        "cat": str(cats[i]),
        "max_lsb": int(per[i]),
        "img_min": int(img.min()),
        "img_max": int(img.max()),
        "img_mean": float(img.mean()),
        "n_nonzero_px": int((img != 0).sum()),
        "board_nz": [[k, int(b[k])] for k in bnz],
        "csim_nz": [[k, int(c[k])] for k in cnz],
    })

# Is the board output of gray_0 a subset/shift of csim values?
def values(nz):
    return sorted(v for _, v in nz)

gray = [r for r in rows if r["cat"] == "const_gray"]
levels = []
for r in gray:
    # name gray_<n>
    levels.append(int(str(r["name"]).split("_")[1]))

# value multiset equality ignoring channel index
same_values = 0
for r in rows:
    if values(r["board_nz"]) == values(r["csim_nz"]):
        same_values += 1

# For the low-gray band, does board match csim of a different level?
csim_by_level = {}
for i, name in enumerate(names):
    if str(name).startswith("gray_"):
        csim_by_level[int(str(name).split("_")[1])] = csim[i]

alias = []
for r in gray:
    lv = int(str(r["name"]).split("_")[1])
    hit = None
    b = board[r["i"]]
    for other, vec in csim_by_level.items():
        if np.array_equal(b, vec):
            hit = other
            break
    alias.append([lv, hit])

out = {
    "n_fail": int(len(fail)),
    "by_cat": {},
    "gray_levels": levels,
    "gray_level_min": int(min(levels)) if levels else None,
    "gray_level_max": int(max(levels)) if levels else None,
    "gray_contiguous": levels == list(range(min(levels), max(levels) + 1)) if levels else None,
    "same_nonzero_values_ignore_channel": same_values,
    "gray_board_equals_csim_of_level": alias,
    "frames": rows,
}
(SYN / "v5_fail_pattern.json").write_text(json.dumps(out))
print("n_fail", out["n_fail"])
print("gray", out["gray_level_min"], out["gray_level_max"], "contiguous", out["gray_contiguous"], "n", len(levels))
print("same values ignore channel", same_values)
print("alias sample", alias[:8], "...", alias[-4:])
print("--- near_black / extreme / chan ---")
for r in rows:
    if r["cat"] != "const_gray":
        print(r["name"], "max", r["max_lsb"], "img", r["img_min"], r["img_max"], "nzpx", r["n_nonzero_px"],
              "board", r["board_nz"], "csim", r["csim_nz"])
