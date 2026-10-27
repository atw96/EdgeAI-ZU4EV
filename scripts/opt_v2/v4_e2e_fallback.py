#!/usr/bin/env python3
"""Same gates as docs/e2e_compare.py.

scipy.stats.binomtest does not import in edgeai_39 (numpy 1.19 vs the
installed scipy). The two-sided exact McNemar p-value is computed here.
"""
import json
import math
from pathlib import Path

import numpy as np

OUT = (Path(__file__).resolve().parents[2] / 'results/opt_v2')


def binom_two_sided(k, n):
    if n == 0:
        return 1.0
    # P(X<=k) + P(X>=n-k) for X~Bin(n, 0.5), k = min(b, c)
    def pmf_le(limit):
        p = 0.0
        term = 2.0 ** (-n)
        for i in range(limit + 1):
            p += term
            term *= (n - i) / (i + 1)
        return p
    return min(1.0, 2.0 * pmf_le(k))


def mcnemar(a_ok, b_ok):
    b = int(((a_ok == 1) & (b_ok == 0)).sum())
    c = int(((a_ok == 0) & (b_ok == 1)).sum())
    p = 1.0 if b + c == 0 else binom_two_sided(min(b, c), b + c)
    return dict(a_only=b, b_only=c, p=float(p))


def main():
    y = np.load(OUT / 'v4_labels_10k.npy')
    kp = np.load(OUT / 'v4_keras_pred_10k.npy')
    bp = np.load(OUT / 'board_pred_reset_each.npy')
    bg = np.load(OUT / 'v4_board_gap_f.npy')
    cg = np.load(OUT / 'v4_csim_gap_prefix_f.npy')
    lat = np.load(OUT / 'board_lat_reset_each.npy')
    n = len(y)
    rep = dict(N=int(n), pass_hard_gate=True)
    rep['top1'] = dict(keras=float((kp == y).mean()), board=float((bp == y).mean()))
    rep['mcnemar_board_vs_keras'] = mcnemar((bp == y).astype(int), (kp == y).astype(int))
    rep['board_vs_keras_top1_gap_pt'] = 100 * (rep['top1']['keras'] - rep['top1']['board'])
    m = len(cg)
    d = np.abs(bg[:m].astype(np.float64) - cg.astype(np.float64))
    rep['gap_board_vs_csim'] = dict(
        M=int(m), max_abs=float(d.max()), mean_abs=float(d.mean()),
        n_images_with_any_diff=int((d.max(axis=1) > 0).sum()))
    if d.max() != 0:
        rep['pass_hard_gate'] = False
    rep['latency_ms'] = dict(
        median=float(np.median(lat)), p99=float(np.percentile(lat, 99)),
        mean=float(lat.mean()), std=float(lat.std()), n=int(len(lat)))
    rep['note'] = 'McNemar p uses a local two-sided binomial; docs/e2e_compare.py could not import scipy.stats in edgeai_39.'
    path = OUT / 'e2e_report.json'
    path.write_text(json.dumps(rep, indent=2), encoding='utf-8')
    print(json.dumps(rep, indent=2))
    print('wrote', path, 'hard', rep['pass_hard_gate'])


if __name__ == '__main__':
    main()
