#!/usr/bin/env python3
"""v11: replace complete array partitions in nnet_conv_stream.h (actual conv path)."""
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CONV_STREAM = REPO / 'notebooks' / 'hls4ml_prj' / 'firmware' / 'nnet_utils' / 'nnet_conv_stream.h'

KERNEL_FACTOR = int(os.environ.get('HLS_KERNEL_CYCLIC_FACTOR', '4'))
RES_FACTOR = int(os.environ.get('HLS_RES_CYCLIC_FACTOR', '4'))
SHIFT_FACTOR = int(os.environ.get('HLS_SHIFT_CYCLIC_FACTOR', '2'))
DATA_FACTOR = int(os.environ.get('HLS_MULTBUF_CYCLIC_FACTOR', '4'))


def _cyclic(var: str, factor: int, dim: int = 1) -> str:
    return (
        '#pragma HLS ARRAY_PARTITION variable = %s cyclic factor = %d dim = %d'
        % (var, factor, dim)
    )


# kernel_data is left fully partitioned. Rewriting it to cyclic factor 4 cuts
# the read ports, and the RF=27 ReuseLoop then schedules at II=8.
# Measured on a stock vs patched Conv2D(16,3,same) from 32x32x3, RF=27:
# 36997 cycles, II=1  vs  263573 cycles, II=8
# (results/opt_v2/p4_micro_csynth.json). That is the conv1a 9.5x.
REPLACEMENTS = [
    (
        '#pragma HLS ARRAY_PARTITION variable = shift_buffer complete dim = 0',
        _cyclic('shift_buffer', SHIFT_FACTOR, 1),
        'shift_buffer',
    ),
    (
        '#pragma HLS ARRAY_PARTITION variable = res_out complete dim = 0',
        _cyclic('res_out', RES_FACTOR, 1),
        'res_out',
    ),
    (
        '#pragma HLS ARRAY_PARTITION variable = data complete',
        _cyclic('data', DATA_FACTOR, 1),
        'mult_buffer data',
    ),
    (
        '#pragma HLS ARRAY_PARTITION variable = res complete',
        _cyclic('res', RES_FACTOR, 1),
        'mult_buffer res',
    ),
]


def main() -> int:
    if not CONV_STREAM.is_file():
        print('ERROR: missing %s' % CONV_STREAM, file=sys.stderr)
        return 1
    text = CONV_STREAM.read_text(encoding='utf-8')
    changed = False
    for old, new, label in REPLACEMENTS:
        count = text.count(old)
        if count == 0:
            print('WARN: pattern not found for %s' % label, file=sys.stderr)
            continue
        text = text.replace(old, new)
        print('patched %s: %d occurrence(s) -> cyclic' % (label, count))
        changed = True
    if changed:
        CONV_STREAM.write_text(text, encoding='utf-8')
    print(
        'conv_stream: kernel_factor=%d res_factor=%d shift_factor=%d data_factor=%d changed=%s'
        % (KERNEL_FACTOR, RES_FACTOR, SHIFT_FACTOR, DATA_FACTOR, changed)
    )
    return 0


if __name__ == '__main__':
    sys.exit(main())
