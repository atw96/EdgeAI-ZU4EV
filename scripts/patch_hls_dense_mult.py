#!/usr/bin/env python3
"""v12: restore dense mult cyclic partition (v10 strip caused config2 synth hang)."""
import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DENSE = REPO / 'notebooks' / 'hls4ml_prj' / 'firmware' / 'nnet_utils' / 'nnet_dense_latency.h'
FACTOR = int(os.environ.get('DENSE_MULT_PARTITION_FACTOR', '16'))
MULT_DECL = '    typename CONFIG_T::accum_t mult[CONFIG_T::n_in * CONFIG_T::n_out];'
CYCLIC = '    #pragma HLS ARRAY_PARTITION variable=mult cyclic factor=%d dim=1' % FACTOR


def main() -> int:
    if not DENSE.is_file():
        print('ERROR: missing %s' % DENSE, file=sys.stderr)
        return 1
    text = DENSE.read_text(encoding='utf-8')
    if CYCLIC in text:
        print('dense mult already cyclic factor=%d' % FACTOR)
        return 0
    if '#pragma HLS ARRAY_PARTITION variable=mult complete' in text:
        text = text.replace(
            '#pragma HLS ARRAY_PARTITION variable=mult complete',
            CYCLIC.strip(),
            1,
        )
        changed = 'complete->cyclic'
    elif re.search(r'#pragma HLS ARRAY_PARTITION variable=mult cyclic factor=\d+ dim=1', text):
        text, n = re.subn(
            r'#pragma HLS ARRAY_PARTITION variable=mult cyclic factor=\d+ dim=1',
            CYCLIC.strip(),
            text,
            count=1,
        )
        changed = 'updated cyclic' if n else 'noop'
    elif MULT_DECL in text:
        text = text.replace(MULT_DECL, MULT_DECL + '\n' + CYCLIC, 1)
        changed = 'inserted cyclic'
    else:
        print('ERROR: mult array declaration not found', file=sys.stderr)
        return 1
    DENSE.write_text(text, encoding='utf-8')
    print('patched dense_latency mult: %s factor=%d' % (changed, FACTOR))
    return 0


if __name__ == '__main__':
    sys.exit(main())
