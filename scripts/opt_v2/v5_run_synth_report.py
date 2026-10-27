#!/usr/bin/env python3
"""Quantize board/csim GAP onto the 1/1024 grid, then run synth_report.

csim_results.log prints about 6 significant digits. Comparing those floats
directly to board_int16/1024 trips the hard gate on print noise. Rounding
both sides to the nearest LSB is the bit-exact comparison used on the 10k set.
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
SYN = REPO / "results" / "opt_v2" / "v5_synth"
SCALE = 1024.0

board = np.load(SYN / "board_gap_synth.npy").astype(np.int32)
csim = np.load(SYN / "csim_gap.npy").astype(np.float64)
keras = np.load(SYN / "keras_gap.npy").astype(np.float64)
if board.shape != csim.shape or keras.shape[0] != board.shape[0]:
    raise SystemExit(f"shape board {board.shape} csim {csim.shape} keras {keras.shape}")

csim_lsb = np.rint(csim * SCALE).astype(np.int32)
board_f = board.astype(np.float64) / SCALE
csim_f = csim_lsb.astype(np.float64) / SCALE
np.save(SYN / "board_gap_f.npy", board_f.astype(np.float32))
np.save(SYN / "csim_gap_q.npy", csim_f.astype(np.float32))

delta = np.abs(board - csim_lsb)
per = delta.max(axis=1)
summary = {
    "n": int(board.shape[0]),
    "max_lsb": int(per.max()),
    "n_mismatch": int((per > 0).sum()),
    "mismatch_index": [int(i) for i in np.where(per > 0)[0]],
}
(SYN / "board_vs_csim_lsb.json").write_text(json.dumps(summary))
print("integer LSB", json.dumps({k: summary[k] for k in ("n", "max_lsb", "n_mismatch")}))

report = REPO / "docs" / "synth_report.py"
if not report.is_file():
    report = (Path(__file__).resolve().parents[2] / 'docs/synth_report.py')
out = REPO / "results" / "opt_v2" / "v5_v3_synth.json"
cmd = [
    sys.executable, str(report),
    "--suite", str(SYN / "synth_suite.npz"),
    "--board", str(SYN / "board_gap_f.npy"),
    "--csim", str(SYN / "csim_gap_q.npy"),
    "--keras", str(SYN / "keras_gap.npy"),
    "--scale", "1024",
    "--nat-max-lsb", "266",
    "--out", str(out),
]
print(" ".join(cmd))
raise SystemExit(subprocess.call(cmd))
