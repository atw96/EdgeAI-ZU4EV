#!/usr/bin/env python3
"""Summarize reuse_factor / implied parallelism from parameters.h."""
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PARAMS = REPO / 'notebooks' / 'hls4ml_prj' / 'firmware' / 'parameters.h'


def main() -> int:
    t = PARAMS.read_text(encoding='utf-8')
    rows = []
    for m in re.finditer(
        r'struct (config\w+)\s*:\s*(\S+)\s*\{(.+?)\n\};',
        t,
        re.S,
    ):
        name, base, body = m.group(1), m.group(2), m.group(3)
        rf_m = re.search(r'reuse_factor = (\d+)', body)
        if not rf_m:
            continue
        rf = int(rf_m.group(1))
        ni = re.search(r'n_in = (\d+)', body)
        no = re.search(r'n_out = (\d+)', body)
        nc = re.search(r'n_chan = (\d+)', body)
        nf = re.search(r'n_filt = (\d+)', body)
        ks = re.search(r'kernel_size = (\d+)', body)
        par = None
        tag = ''
        if ks and nc and nf:
            prod = int(ks.group(1)) * int(nc.group(1)) * int(nf.group(1))
            par = prod / rf
            tag = 'conv kcn=%d' % prod
        elif ni and no:
            prod = int(ni.group(1)) * int(no.group(1))
            par = prod / rf
            tag = 'dense in*out=%d' % prod
        elif ni:
            prod = int(ni.group(1))
            par = prod / rf
            tag = 'n_in=%d' % prod
        rows.append((par if par is not None else 0, rf, name, base, tag))
    rows.sort(reverse=True)
    print('=== configs by implied parallelism (high -> low) ===')
    for par, rf, name, base, tag in rows[:40]:
        print('%8.1f  RF=%5d  %-20s %-28s %s' % (par, rf, name, base, tag))
    rf1 = [r for r in rows if r[1] == 1]
    print('\n=== RF=1 count: %d ===' % len(rf1))
    for par, rf, name, base, tag in sorted(rf1, reverse=True)[:15]:
        print('%8.1f  %-20s %s' % (par, name, tag))
    return 0


if __name__ == '__main__':
    sys.exit(main())
