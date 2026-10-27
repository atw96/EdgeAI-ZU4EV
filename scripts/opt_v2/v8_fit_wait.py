#!/usr/bin/env python3
from pathlib import Path
"""Fit T_wait from the X1 n1000 rows. window_ms column fed to the fitter is T_wait."""
import csv
import os
import sys

import numpy as np

REPO = str(Path(__file__).resolve().parents[2])
src = os.path.join(REPO, "results/opt_v2/v8/v8_ladder.csv")
dst = os.path.join(REPO, "results/opt_v2/v8/v8_wait_fit.csv")
rows = [r for r in csv.DictReader(open(src)) if r["tag"] == "n1000"]
with open(dst, "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=["f_mhz", "window_ms"])
    w.writeheader()
    for r in rows:
        w.writerow({"f_mhz": r["f_mhz"], "window_ms": r["wait_ms"]})
sys.path.insert(0, os.path.join(REPO, "docs"))
from latency_model import fit

fit(dst)
rc1 = [r for r in csv.DictReader(open(src)) if r["tag"] == "rc1"][0]
old = [r for r in csv.DictReader(open(src)) if r["tag"] == "old"][0]
rw, ow = float(rc1["window_ms"]), float(old["window_ms"])
rwait, owait = float(rc1["wait_ms"]), float(old["wait_ms"])
print("T_window ratio old/rc1 = %.4f  (%.4f / %.4f)" % (ow / rw, ow, rw))
print("T_wait ratio old/rc1 = %.4f  (%.4f / %.4f)" % (owait / rwait, owait, rwait))
print("n1000 max rel vs 1.719*99.942/f:")
for r in rows:
    pred = 1.719 * 99.942 / float(r["f_mhz"])
    meas = float(r["wait_ms"])
    print("  div0 %s  %.4f vs %.4f  %+.2f%%" % (r["div0"], meas, pred, 100 * (meas - pred) / pred))
