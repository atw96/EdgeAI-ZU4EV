#!/usr/bin/env python3
"""v13: same antihang fixes for dense_resource (used by config*_mult)."""
import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RESOURCE = REPO / 'notebooks' / 'hls4ml_prj' / 'firmware' / 'nnet_utils' / 'nnet_dense_resource.h'
FACTOR = int(os.environ.get('DENSE_BIAS_CYCLIC_FACTOR', '4'))

INST_RE = re.compile(
    r'\n\s*#pragma HLS function_instantiate variable=weights,biases\n'
)
BIAS_COMPLETE = '#pragma HLS ARRAY_PARTITION variable=biases complete'
ACC_COMPLETE = '#pragma HLS ARRAY_PARTITION variable=acc complete'
BIAS_CYCLIC = (
    '#pragma HLS ARRAY_PARTITION variable=biases cyclic factor=%d dim=1' % FACTOR
)
ACC_CYCLIC = (
    '#pragma HLS ARRAY_PARTITION variable=acc cyclic factor=%d dim=1' % FACTOR
)
TMPMULT_COMPLETE = '#pragma HLS ARRAY_PARTITION variable=tmpmult complete'
TMPMULT_CYCLIC = (
    '#pragma HLS ARRAY_PARTITION variable=tmpmult cyclic factor=%d dim=1' % FACTOR
)
MULT_COMPLETE = '#pragma HLS ARRAY_PARTITION variable=mult complete'
MULT_CYCLIC = (
    '#pragma HLS ARRAY_PARTITION variable=mult cyclic factor=%d dim=1' % FACTOR
)


def main() -> int:
    if not RESOURCE.is_file():
        print('ERROR: missing %s' % RESOURCE, file=sys.stderr)
        return 1
    text = RESOURCE.read_text(encoding='utf-8')
    changed = False

    new_text, n = INST_RE.subn('\n', text)
    if n:
        print('removed %d function_instantiate pragma(s)' % n)
        text = new_text
        changed = True
    else:
        print('function_instantiate already absent in dense_resource')

    for old, new, label in (
        (BIAS_COMPLETE, BIAS_CYCLIC, 'biases'),
        (ACC_COMPLETE, ACC_CYCLIC, 'acc'),
        (TMPMULT_COMPLETE, TMPMULT_CYCLIC, 'tmpmult'),
        (MULT_COMPLETE, MULT_CYCLIC, 'mult'),
    ):
        count = text.count(old)
        if count:
            text = text.replace(old, new)
            print('%s complete -> cyclic factor=%d (%d)' % (label, FACTOR, count))
            changed = True

    if changed:
        RESOURCE.write_text(text, encoding='utf-8')
    print('dense_resource_antihang changed=%s factor=%d' % (changed, FACTOR))
    return 0


if __name__ == '__main__':
    sys.exit(main())
