#!/usr/bin/env python3
"""Plan B: limit dense mult array partition to avoid HLS OOM on 32GB host."""
import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DENSE_LATENCY = REPO / 'notebooks' / 'hls4ml_prj' / 'firmware' / 'nnet_utils' / 'nnet_dense_latency.h'
BUILD_TCL = REPO / 'notebooks' / 'hls4ml_prj' / 'build_prj.tcl'
MULT_COMPLETE = '#pragma HLS ARRAY_PARTITION variable=mult complete'
MULT_CYCLIC_TMPL = '#pragma HLS ARRAY_PARTITION variable=mult cyclic factor={factor} dim=1'


def patch_dense_header(factor: int) -> bool:
    text = DENSE_LATENCY.read_text(encoding='utf-8')
    cyclic = MULT_CYCLIC_TMPL.format(factor=factor)
    if cyclic in text:
        print('dense_latency mult already cyclic factor=%d' % factor)
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
            print('ERROR: no mult partition pragma found', file=sys.stderr)
            return False
    DENSE_LATENCY.write_text(text, encoding='utf-8')
    print('patched mult complete -> cyclic factor=%d' % factor)
    return True


def patch_build_tcl(max_size: int) -> bool:
    text = BUILD_TCL.read_text(encoding='utf-8')
    new_line = 'catch {config_array_partition -maximum_size %d}' % max_size
    if new_line in text:
        print('build_prj.tcl maximum_size already %d' % max_size)
        return False
    new_text, n = re.subn(
        r'catch \{config_array_partition -maximum_size \d+\}',
        new_line,
        text,
        count=1,
    )
    if n == 0:
        print('ERROR: config_array_partition line not found', file=sys.stderr)
        return False
    BUILD_TCL.write_text(new_text, encoding='utf-8')
    print('patched build_prj.tcl maximum_size -> %d' % max_size)
    return True


def main() -> int:
    factor = int(os.environ.get('DENSE_MULT_PARTITION_FACTOR', '16'))
    max_size = int(os.environ.get('HLS_ARRAY_PARTITION_MAX', '4096'))
    h = patch_dense_header(factor)
    t = patch_build_tcl(max_size)
    print('dense_patched=%s tcl_patched=%s factor=%d max_size=%d' % (h, t, factor, max_size))
    return 0


if __name__ == '__main__':
    sys.exit(main())
