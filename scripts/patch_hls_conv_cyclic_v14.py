#!/usr/bin/env python3
"""v14: tighten conv_stream cyclic factors (4 -> 2) for LUT."""
import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CONV = REPO / 'notebooks' / 'hls4ml_prj' / 'firmware' / 'nnet_utils' / 'nnet_conv_stream.h'
KF = int(os.environ.get('HLS_KERNEL_CYCLIC_FACTOR', '2'))
RF = int(os.environ.get('HLS_RES_CYCLIC_FACTOR', '2'))
SF = int(os.environ.get('HLS_SHIFT_CYCLIC_FACTOR', '2'))


def _set_factor(text, var, factor, dim):
    pat = r'#pragma HLS ARRAY_PARTITION variable = %s cyclic factor = \d+ dim = %d' % (
        var, dim)
    rep = '#pragma HLS ARRAY_PARTITION variable = %s cyclic factor = %d dim = %d' % (
        var, factor, dim)
    new, n = re.subn(pat, rep, text)
    return new, n


def main() -> int:
    if not CONV.is_file():
        print('ERROR: missing %s' % CONV, file=sys.stderr)
        return 1
    text = CONV.read_text(encoding='utf-8')
    total = 0
    for var, fac, dim in (
        ('shift_buffer', SF, 1),
        ('kernel_data', KF, 1),
        ('res_out', RF, 1),
        ('data', KF, 1),
        ('res', RF, 1),
    ):
        text, n = _set_factor(text, var, fac, dim)
        if n:
            print('set %s cyclic factor=%d (%d)' % (var, fac, n))
            total += n
    CONV.write_text(text, encoding='utf-8')
    print('conv_cyclic_v14 updates=%d' % total)
    return 0


if __name__ == '__main__':
    sys.exit(main())
