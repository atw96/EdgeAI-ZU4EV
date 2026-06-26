#!/usr/bin/env python3
"""v13: stop dense_latency 203-622 clone explosion (biases complete + function_instantiate)."""
import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DENSE = REPO / 'notebooks' / 'hls4ml_prj' / 'firmware' / 'nnet_utils' / 'nnet_dense_latency.h'
FACTOR = int(os.environ.get('DENSE_BIAS_CYCLIC_FACTOR', '4'))

INSTANTIATE = '#pragma HLS function_instantiate variable=weights,biases'
BIAS_COMPLETE = '#pragma HLS ARRAY_PARTITION variable=biases complete'
ACC_COMPLETE = '#pragma HLS ARRAY_PARTITION variable=acc complete'
BIAS_CYCLIC = (
    '#pragma HLS ARRAY_PARTITION variable=biases cyclic factor=%d dim=1' % FACTOR
)
ACC_CYCLIC = (
    '#pragma HLS ARRAY_PARTITION variable=acc cyclic factor=%d dim=1' % FACTOR
)


def main() -> int:
    if not DENSE.is_file():
        print('ERROR: missing %s' % DENSE, file=sys.stderr)
        return 1
    text = DENSE.read_text(encoding='utf-8')
    changed = False

    if INSTANTIATE in text:
        text = text.replace(INSTANTIATE + '\n', '', 1)
        print('removed function_instantiate on weights,biases')
        changed = True
    elif 'function_instantiate variable=weights,biases' in text:
        text = re.sub(
            r'\n\s*#pragma HLS function_instantiate variable=weights,biases[^\n]*\n',
            '\n',
            text,
            count=1,
        )
        print('removed function_instantiate (regex)')
        changed = True
    else:
        print('function_instantiate already absent')

    if BIAS_COMPLETE in text:
        text = text.replace(BIAS_COMPLETE, BIAS_CYCLIC, 1)
        print('biases complete -> cyclic factor=%d' % FACTOR)
        changed = True
    elif BIAS_CYCLIC in text:
        print('biases already cyclic factor=%d' % FACTOR)
    else:
        print('WARN: biases partition pragma not found', file=sys.stderr)

    if ACC_COMPLETE in text:
        text = text.replace(ACC_COMPLETE, ACC_CYCLIC, 1)
        print('acc complete -> cyclic factor=%d' % FACTOR)
        changed = True
    elif ACC_CYCLIC in text:
        print('acc already cyclic factor=%d' % FACTOR)
    else:
        print('WARN: acc partition pragma not found', file=sys.stderr)

    if changed:
        DENSE.write_text(text, encoding='utf-8')
    print('dense_antihang changed=%s factor=%d' % (changed, FACTOR))
    return 0


if __name__ == '__main__':
    sys.exit(main())
