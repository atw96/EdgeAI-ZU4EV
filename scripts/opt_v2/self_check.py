#!/usr/bin/env python3
"""Offline checks for the v2 glue. No HLS, no board, no weight files."""
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'scripts'))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from lut_extrapolate import fit  # noqa: E402
from mcnemar_pair import mcnemar  # noqa: E402
from rf_planner import dense_variant, layers, valid_rf  # noqa: E402
from set_rf import VARIANTS, check  # noqa: E402


def main():
    rows = {row['name']: row for row in layers()}
    illegal = [
        ('conv2a', 180), ('conv2b', 225), ('conv3a', 270), ('conv3b', 324),
        ('conv2a', 60), ('conv2b', 75),
    ]
    for name, rf in illegal:
        row = rows[name]
        if valid_rf(row['n_in'], row['n_out'], rf):
            raise SystemExit('expected illegal RF %s=%s' % (name, rf))
    for name, rfs in VARIANTS.items():
        channels = (32, 32, 40, 40, 48, 48) if name.startswith('B2-') else (16, 16, 20, 20, 24, 24)
        check(rfs, channels)
        if name != 'P4':
            for row, rf in zip(layers(ch=channels), rfs):
                if dense_variant(row['n_in'], rf) != 'rf_leq_nin':
                    raise SystemExit('%s %s not rf_leq_nin' % (name, row['name']))

    a = np.array([1, 1, 0, 0, 1, 0], dtype=np.uint8)
    c = np.array([1, 0, 1, 0, 1, 0], dtype=np.uint8)
    stats = mcnemar(a, c)
    if stats['discordant'] != 2:
        raise SystemExit('mcnemar discordant %s' % stats)
    if not 0.0 <= stats['pvalue'] <= 1.0:
        raise SystemExit('bad pvalue %s' % stats)

    same = fit([(24, 24702, 'a'), (120, 40000, 'b')], next_sum_p=188)
    if not same['allow_next']:
        raise SystemExit('expected LUT headroom, got %s' % same)
    blocked = fit([(24, 24702, 'a'), (120, 55000, 'b')], next_sum_p=452, limit=60000)
    if blocked['allow_next']:
        raise SystemExit('expected LUT block, got %s' % blocked)

    from experiment_record import write_record
    first = write_record({'variant': 'self_check', 'notes': 'glue'}, 'self_check')
    second = write_record({'variant': 'self_check', 'notes': 'glue-2'}, 'self_check')
    if first == second or not first.is_file() or not second.is_file():
        raise SystemExit('experiment records collided: %s %s' % (first, second))
    first.unlink()
    second.unlink()
    print(json.dumps({'self_check': 'ok'}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
