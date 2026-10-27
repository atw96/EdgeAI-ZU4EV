#!/usr/bin/env python3
from pathlib import Path
"""Pack X2 payloads, int32 LSB golden, and float32 dense weights for the C hot path."""
import os

import numpy as np

REPO = str(Path(__file__).resolve().parents[2])
OUT = os.path.join(REPO, "results/opt_v2/v8")


def as_lsb(arr):
    a = np.asarray(arr)
    if a.dtype.kind == "f":
        return np.rint(a.astype(np.float64) * 1024.0).astype(np.int32)
    return a.astype(np.int32)


def dump(tag, payloads, golden_lsb, weight, bias):
    x = golden_lsb.astype(np.float32) / 1024.0
    logits = x @ weight + bias
    top1 = logits.argmax(axis=1).astype(np.int32)
    os.makedirs(OUT, exist_ok=True)
    payloads.astype(np.uint8).tofile(os.path.join(OUT, tag + "_payloads.bin"))
    golden_lsb.astype(np.int32).tofile(os.path.join(OUT, tag + "_golden.bin"))
    top1.tofile(os.path.join(OUT, tag + "_top1.bin"))
    print(tag, payloads.shape[0], "top1", float((top1 == logits.argmax(1)).mean()))


def main():
    os.makedirs(OUT, exist_ok=True)
    dense = np.load(os.path.join(REPO, "deploy/dense_head.npz"))
    weight = np.asarray(dense["weight"], dtype=np.float32)
    bias = np.asarray(dense["bias"], dtype=np.float32)
    print("weight", weight.shape, weight.dtype, "bias", bias.shape, bias.dtype)
    if weight.shape == (10, 24):
        weight = weight.T.copy()
    if weight.shape != (24, 10) or bias.shape != (10,):
        raise SystemExit("unexpected dense shape %s %s" % (weight.shape, bias.shape))
    weight.tofile(os.path.join(OUT, "dense_w.bin"))
    bias.tofile(os.path.join(OUT, "dense_b.bin"))

    kat = np.load(os.path.join(REPO, "results/opt_v2/v5_synth/kat_packed.npz"))
    kat_g = as_lsb(np.load(os.path.join(REPO, "results/opt_v2/v5_synth/kat_golden.npz"))["gap"])
    dump("kat", kat["payloads"], kat_g, weight, bias)

    bench = np.load(os.path.join(REPO, "results/opt_v2/bench10k_packed.npz"))
    gold = as_lsb(np.load(os.path.join(REPO, "results/opt_v2/v5_v2/board_gap_v2_rc1.npy")))
    n = min(len(bench["payloads"]), len(gold), 10000)
    dump("bench", bench["payloads"][:n], gold[:n], weight, bias)


if __name__ == "__main__":
    main()
