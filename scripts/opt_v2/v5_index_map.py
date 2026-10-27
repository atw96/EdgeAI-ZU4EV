#!/usr/bin/env python3
"""Stable csim-index -> board-index map on frames where each nonzero value is unique."""
import json
from collections import Counter
from pathlib import Path

import numpy as np

SYN = (Path(__file__).resolve().parents[2] / 'results/opt_v2/v5_synth')
board = np.load(SYN / "board_gap_synth.npy").astype(np.int32)
csim = np.rint(np.load(SYN / "csim_gap.npy").astype(np.float64) * 1024.0).astype(np.int32)
fail = np.where(np.abs(board - csim).max(1) > 0)[0]
reloc = Counter()
missing = Counter()
ambiguous = Counter()
same = Counter()
for i in fail:
    b, c = board[i], csim[i]
    for j in range(24):
        v = int(c[j])
        if v == 0:
            continue
        hits = [k for k in range(24) if int(b[k]) == v]
        if len(hits) == 0:
            missing[j] += 1
        elif len(hits) > 1:
            ambiguous[j] += 1
        elif hits[0] == j:
            same[j] += 1
        else:
            reloc[(j, hits[0])] += 1

print("reloc", json.dumps([{"csim": a, "board": b, "n": n} for (a, b), n in sorted(reloc.items())]))
print("same_index", dict(sorted(same.items())))
print("missing", dict(sorted(missing.items())))
print("ambiguous", dict(sorted(ambiguous.items())))
