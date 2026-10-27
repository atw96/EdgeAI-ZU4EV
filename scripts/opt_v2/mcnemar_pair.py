#!/usr/bin/env python3
"""Exact McNemar test on two per-sample correct/incorrect arrays. v2 section 7."""
import argparse
import json
import math
from pathlib import Path

import numpy as np


def _binom_sf_two_sided(k, n):
    """Two-sided exact test of k successes in n trials, p=0.5, using the smaller count."""
    if n <= 0:
        return 1.0
    try:
        from scipy.stats import binomtest
        return float(binomtest(k, n, 0.5).pvalue)
    except Exception:
        pass
    try:
        from scipy.stats import binom_test
        return float(binom_test(k, n, 0.5))
    except Exception:
        pass
    # sum_{i=0..k} + sum_{i=n-k..n} of Binomial(n, 0.5), k = min(b, cc)
    tail = sum(math.comb(n, i) for i in range(0, k + 1))
    p = tail * 2.0 / float(2 ** n)
    return min(1.0, p)


def mcnemar(a, c):
    a = np.asarray(a).astype(np.int32).ravel()
    c = np.asarray(c).astype(np.int32).ravel()
    if a.shape != c.shape:
        raise ValueError('shape mismatch %s vs %s' % (a.shape, c.shape))
    b = int(((a == 1) & (c == 0)).sum())
    cc = int(((a == 0) & (c == 1)).sum())
    discordant = b + cc
    pvalue = _binom_sf_two_sided(min(b, cc), discordant) if discordant else 1.0
    return {
        'n': int(a.size),
        'a_only_correct': b,
        'c_only_correct': cc,
        'discordant': discordant,
        'top1_a': round(100.0 * float(a.mean()), 4),
        'top1_c': round(100.0 * float(c.mean()), 4),
        'pvalue': pvalue,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('a_npy')
    ap.add_argument('c_npy')
    ap.add_argument('--out', default='')
    args = ap.parse_args()
    result = mcnemar(np.load(args.a_npy), np.load(args.c_npy))
    text = json.dumps(result, indent=2)
    if args.out:
        Path(args.out).write_text(text, encoding='utf-8')
    print(text)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
