#!/usr/bin/env python3
"""v15: allow inlining compute_output_buffer_2d to cut standalone module overhead."""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CONV = REPO / 'notebooks' / 'hls4ml_prj' / 'firmware' / 'nnet_utils' / 'nnet_conv_stream.h'

OLD = '    #pragma HLS INLINE OFF'
NEW = '    #pragma HLS INLINE recursive'


def main() -> int:
    if not CONV.is_file():
        print('ERROR: missing %s' % CONV, file=sys.stderr)
        return 1
    text = CONV.read_text(encoding='utf-8')
    count = text.count(OLD)
    if count == 0:
        if NEW in text:
            print('compute_output_buffer already INLINE recursive')
            return 0
        print('WARN: INLINE OFF not found', file=sys.stderr)
        return 1
    text = text.replace(OLD, NEW)
    CONV.write_text(text, encoding='utf-8')
    print('patched compute_output_buffer INLINE OFF -> recursive (%d)' % count)
    return 0


if __name__ == '__main__':
    sys.exit(main())
