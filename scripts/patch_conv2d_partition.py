#!/usr/bin/env python3
"""Plan B for conv2d: replace mult complete partition to cut LUT (v9)."""
import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CONV_LATENCY = REPO / 'notebooks' / 'hls4ml_prj' / 'firmware' / 'nnet_utils' / 'nnet_conv2d_latency.h'
MULT_COMPLETE = '#pragma HLS ARRAY_PARTITION variable=mult complete'
MULT_CYCLIC_TMPL = '#pragma HLS ARRAY_PARTITION variable=mult cyclic factor={factor} dim=1'


def patch_conv_header(factor: int) -> bool:
    if not CONV_LATENCY.exists():
        print('ERROR: missing %s' % CONV_LATENCY, file=sys.stderr)
        return False
    text = CONV_LATENCY.read_text(encoding='utf-8')
    cyclic = MULT_CYCLIC_TMPL.format(factor=factor)
    if cyclic in text:
        print('conv2d mult already cyclic factor=%d' % factor)
        return False
    if MULT_COMPLETE in text:
        text = text.replace(MULT_COMPLETE, cyclic, 1)
    else:
        text, n = re.subn(
            r'#pragma HLS ARRAY_PARTITION variable=mult cyclic factor=\d+ dim=1',
            cyclic,
            text,
            count=1,
        )
        if n == 0:
            print('ERROR: conv2d mult partition pragma not found', file=sys.stderr)
            return False
    CONV_LATENCY.write_text(text, encoding='utf-8')
    print('patched conv2d mult complete -> cyclic factor=%d' % factor)
    return True


def main() -> int:
    factor = int(os.environ.get('CONV_MULT_PARTITION_FACTOR', '2'))
    ok = patch_conv_header(factor)
    print('conv2d_patched=%s factor=%d' % (ok, factor))
    return 0


if __name__ == '__main__':
    sys.exit(main())
