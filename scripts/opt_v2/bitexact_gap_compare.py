#!/usr/bin/env python3
"""Compare two csim GAP logs. RF-only changes must be bit-exact when accum width is enough."""
import argparse
import sys
from pathlib import Path

import numpy as np


def load_lines(path):
    text = Path(path).read_text(encoding='utf-8').strip().splitlines()
    if not text:
        raise SystemExit('empty %s' % path)
    rows = []
    for line in text:
        rows.append([float(x) for x in line.split()])
    return text, np.asarray(rows, dtype=np.float64)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('baseline')
    ap.add_argument('candidate')
    ap.add_argument('--n', type=int, default=0, help='Compare the first N lines; 0 means all overlap')
    args = ap.parse_args()
    base_text, base = load_lines(args.baseline)
    cand_text, cand = load_lines(args.candidate)
    n = min(len(base_text), len(cand_text))
    if args.n:
        n = min(n, args.n)
    if n == 0:
        print('ERROR: no overlapping lines', file=sys.stderr)
        return 1
    base_n = base[:n]
    cand_n = cand[:n]
    text_equal = base_text[:n] == cand_text[:n]
    max_abs = float(np.max(np.abs(base_n - cand_n)))
    print('n=%d text_equal=%s max_abs=%g' % (n, text_equal, max_abs))
    if not text_equal and max_abs != 0.0:
        print('ERROR: GAP not bit-exact; check accumulator width before continuing', file=sys.stderr)
        return 1
    print('bit_exact=True')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
