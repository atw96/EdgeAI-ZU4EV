#!/usr/bin/env python3
"""See whether failing frames keep csim values and only move channel indices."""
import numpy as np
from pathlib import Path

SYN = (Path(__file__).resolve().parents[2] / 'results/opt_v2/v5_synth')
suite = np.load(SYN / "synth_suite.npz", allow_pickle=True)
names = [str(x) for x in suite["names"]]
board = np.load(SYN / "board_gap_synth.npy").astype(np.int32)
csim = np.rint(np.load(SYN / "csim_gap.npy").astype(np.float64) * 1024.0).astype(np.int32)

def show(i):
    b, c = board[i], csim[i]
    print("\n", i, names[i], "max", int(np.abs(b - c).max()))
    print(" board", b.tolist())
    print(" csim ", c.tolist())
    # which csim channels equal each board channel
    for k in range(24):
        if b[k] == 0 and c[k] == 0:
            continue
        hits = [j for j in range(24) if c[j] == b[k]]
        print(f"  board[{k}]={b[k]} csim[{k}]={c[k]} value_in_csim_at {hits}")

for name in ("gray_0", "gray_51", "gray_52", "gray_40", "extreme_111", "nearblack_k64_v8"):
    show(names.index(name))

# Across all fails: fraction of board nonzero values that occur somewhere in that frame's csim
fail = np.where(np.abs(board - csim).max(1) > 0)[0]
kept = lost = extra = 0
for i in fail:
    bset = [int(v) for v in board[i] if v != 0]
    cset = [int(v) for v in csim[i] if v != 0]
    for v in bset:
        if v in cset:
            kept += 1
        else:
            extra += 1
    for v in cset:
        if v not in bset:
            lost += 1
print("\nnonzero value accounting kept", kept, "extra_on_board", extra, "missing_from_board", lost)
