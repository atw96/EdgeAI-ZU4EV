#!/usr/bin/env python3
"""KAT = 16 natural images + the three synthetic frames already known to match csim.

Black is intentionally absent.
"""
import numpy as np
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "results" / "opt_v2" / "v5_synth"
nat = np.load(REPO / "results" / "opt_v2" / "bench10k_packed.npz")
suite = np.load(OUT / "synth_packed.npz", allow_pickle=True)
names = [str(x) for x in suite["names"]]
want = ["extreme_111", "checker_inv_p1", "extreme_001"]
idx = [names.index(w) for w in want]
payloads = np.concatenate([nat["payloads"][:16], suite["payloads"][idx]], axis=0)
labels = np.zeros(len(payloads), np.int32)
kat_names = ["natural_%02d" % i for i in range(16)] + want
np.savez(OUT / "kat_packed.npz", payloads=payloads, labels=labels, names=np.array(kat_names))

lines = (REPO / "results" / "opt_v2" / "v4_csim_10k.log").read_text().splitlines()
nat_gap = np.array([[float(x) for x in lines[i].split()] for i in range(16)], dtype=np.float64)
ext = (REPO / "results" / "opt_v2" / "v4_csim_extreme.log").read_text().splitlines()
# previous extreme order: black, white, checker, sat
white = np.array([float(x) for x in ext[1].split()])
checker = np.array([float(x) for x in ext[2].split()])
sat = np.array([float(x) for x in ext[3].split()])
golden = np.vstack([nat_gap, white, checker, sat])
np.savez(
    OUT / "kat_golden.npz",
    gap=golden,
    names=np.array(kat_names),
    bit_md5="334e27454dcb05d179d6d188b7d404c3",
)
print("kat", len(payloads), "golden", golden.shape)
