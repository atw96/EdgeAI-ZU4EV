#!/usr/bin/env python3
"""v10: strip mult array partitions + shrink conv data_buf to cut HLS peak RAM."""
import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DENSE = REPO / 'notebooks' / 'hls4ml_prj' / 'firmware' / 'nnet_utils' / 'nnet_dense_latency.h'
CONV = REPO / 'notebooks' / 'hls4ml_prj' / 'firmware' / 'nnet_utils' / 'nnet_conv2d_latency.h'
BUILD = REPO / 'notebooks' / 'hls4ml_prj' / 'build_prj.tcl'

MULT_PRAGMA = re.compile(
    r'\n\s*#pragma HLS ARRAY_PARTITION variable=mult[^\n]*\n',
)
DATA_BUF_COMPLETE = '#pragma HLS ARRAY_PARTITION variable=data_buf complete dim=0'
DATA_BUF_CYCLIC = '#pragma HLS ARRAY_PARTITION variable=data_buf cyclic factor=2 dim=1'


def strip_mult_partition(path: Path, label: str) -> bool:
    text = path.read_text(encoding='utf-8')
    if 'ARRAY_PARTITION variable=mult' not in text:
        print('%s: no mult partition pragma' % label)
        return False
    new_text, n = MULT_PRAGMA.subn('\n', text, count=1)
    if n == 0:
        print('ERROR: could not strip mult partition in %s' % path, file=sys.stderr)
        return False
    path.write_text(new_text, encoding='utf-8')
    print('stripped mult ARRAY_PARTITION in %s' % label)
    return True


def patch_data_buf() -> bool:
    text = CONV.read_text(encoding='utf-8')
    if DATA_BUF_CYCLIC in text:
        print('conv2d data_buf already cyclic factor=2')
        return False
    if DATA_BUF_COMPLETE not in text:
        print('ERROR: data_buf complete pragma not found', file=sys.stderr)
        return False
    text = text.replace(DATA_BUF_COMPLETE, DATA_BUF_CYCLIC, 1)
    CONV.write_text(text, encoding='utf-8')
    print('patched conv2d data_buf complete -> cyclic factor=2 dim=1')
    return True


def patch_max_size(max_size: int) -> bool:
    text = BUILD.read_text(encoding='utf-8')
    new_line = 'catch {config_array_partition -maximum_size %d}' % max_size
    if new_line in text:
        return False
    new_text, n = re.subn(
        r'catch \{config_array_partition -maximum_size \d+\}',
        new_line,
        text,
        count=1,
    )
    if n == 0:
        print('ERROR: config_array_partition not found in build_prj.tcl', file=sys.stderr)
        return False
    BUILD.write_text(new_text, encoding='utf-8')
    print('patched build_prj.tcl maximum_size -> %d' % max_size)
    return True


def main() -> int:
    max_size = int(os.environ.get('HLS_ARRAY_PARTITION_MAX', '256'))
    d = strip_mult_partition(DENSE, 'dense_latency')
    c = strip_mult_partition(CONV, 'conv2d_latency')
    b = patch_data_buf()
    t = patch_max_size(max_size)
    print('lowmem: dense=%s conv=%s data_buf=%s tcl=%s max_size=%d' % (d, c, b, t, max_size))
    return 0


if __name__ == '__main__':
    sys.exit(main())
