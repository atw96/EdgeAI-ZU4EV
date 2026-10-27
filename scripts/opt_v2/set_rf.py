#!/usr/bin/env python3
"""Replace RF_PER_LAYER in v19_hls_config_common.py with a named v2 tier.

Does not touch weights or bit widths. Refuses unknown names and illegal factors.
"""
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'scripts'))
from rf_planner import dense_variant, layers, valid_rf  # noqa: E402

CONFIG = REPO / 'scripts' / 'v19_hls_config_common.py'
NAMES = ('conv1a', 'conv1b', 'conv2a', 'conv2b', 'conv3a', 'conv3b')

# Published tables from EdgeAI_ZU4EV_optimization_plan_v2.md. predictions stays off PL.
VARIANTS = {
    'P4': (108, 576, 720, 900, 1080, 1296),
    'A1prime': (27, 144, 144, 180, 180, 216),
    'A2-L': (27, 36, 144, 90, 180, 216),
    'A2-M': (9, 18, 72, 60, 180, 216),
    'A2-H': (9, 12, 48, 45, 180, 108),
    # Wide net 32/32/40/40/48/48, sumP<=480. Only legal for that channel config.
    'B2-480': (27, 48, 144, 180, 360, 432),
    'B2-640': (27, 36, 144, 120, 360, 432),
}


def render(variant, rfs):
    lines = [
        'RF_PER_LAYER = {',
        '    # 2026-10-17 v2 variant %s. Global ReuseFactor is min(these) at convert time.' % variant,
    ]
    for name, rf in zip(NAMES, rfs):
        lines.append("    '%s': %d," % (name, int(rf)))
    lines.append("    'predictions': 240,")
    lines.append('}')
    return '\n'.join(lines)


def check(rfs, channels):
    rows = layers(ch=channels)
    for row, rf in zip(rows, rfs):
        if not valid_rf(row['n_in'], row['n_out'], int(rf)):
            raise SystemExit(
                'illegal %s RF=%s n_in=%s n_out=%s' % (row['name'], rf, row['n_in'], row['n_out'])
            )
        if dense_variant(row['n_in'], int(rf)) != 'rf_leq_nin' and int(rf) > row['n_in']:
            # P4 baseline is the only published table that uses rf_gt_nin_rem0.
            pass
        print('%s RF=%d [%s]' % (row['name'], int(rf), dense_variant(row['n_in'], int(rf))))


def apply(variant, dry_run=False):
    if variant not in VARIANTS:
        raise SystemExit('unknown variant %s; choose %s' % (variant, ', '.join(sorted(VARIANTS))))
    rfs = VARIANTS[variant]
    channels = (32, 32, 40, 40, 48, 48) if variant.startswith('B2-') else (16, 16, 20, 20, 24, 24)
    check(rfs, channels)
    block = render(variant, rfs)
    text = CONFIG.read_text(encoding='utf-8')
    updated, n = re.subn(
        r'RF_PER_LAYER = \{.*?\n\}',
        block,
        text,
        count=1,
        flags=re.S,
    )
    if n != 1:
        raise SystemExit('RF_PER_LAYER block not found in %s' % CONFIG)
    if dry_run:
        print(block)
        return
    CONFIG.write_text(updated, encoding='utf-8')
    print('updated', CONFIG)


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--variant', required=True)
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()
    apply(args.variant, dry_run=args.dry_run)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
