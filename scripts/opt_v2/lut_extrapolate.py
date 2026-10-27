#!/usr/bin/env python3
"""Linear LUT vs sumP fit. Exit 2 when the next tier is predicted above 60000 LUT."""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
OUT_DIR = REPO / 'results' / 'opt_v2'
LUT_LIMIT = 60000


def _points_from_dir(directory):
    points = []
    for path in sorted(Path(directory).glob('*.json')):
        try:
            doc = json.loads(path.read_text(encoding='utf-8'))
        except Exception:
            continue
        sum_p = doc.get('sumP')
        lut = doc.get('impl_LUT')
        if lut is None and isinstance(doc.get('csynth_util'), dict):
            lut = doc['csynth_util'].get('LUT')
        if sum_p is None or lut is None:
            continue
        points.append((float(sum_p), float(lut), path.name))
    return points


def fit(points, next_sum_p, limit=LUT_LIMIT):
    if len(points) < 2:
        return {
            'ok': False,
            'reason': 'need at least 2 (sumP, LUT) points',
            'n_points': len(points),
            'allow_next': False,
        }
    xs = np.array([p[0] for p in points], dtype=np.float64)
    ys = np.array([p[1] for p in points], dtype=np.float64)
    slope, intercept = np.polyfit(xs, ys, 1)
    pred = float(slope * next_sum_p + intercept)
    return {
        'ok': True,
        'n_points': len(points),
        'points': [{'sumP': p[0], 'LUT': p[1], 'file': p[2]} for p in points],
        'slope': slope,
        'intercept': intercept,
        'next_sumP': next_sum_p,
        'predicted_LUT': pred,
        'limit': limit,
        'allow_next': pred <= limit,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--next-sum-p', type=float, required=True)
    ap.add_argument('--dir', default=str(OUT_DIR))
    ap.add_argument('--limit', type=float, default=LUT_LIMIT)
    args = ap.parse_args()
    result = fit(_points_from_dir(args.dir), args.next_sum_p, args.limit)
    print(json.dumps(result, indent=2))
    if not result.get('allow_next'):
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
