#!/usr/bin/env python3
"""P5 experiment: pipeline IndexLoop inside dense_resource_rf_gt_nin_rem0.

Do not add this to the default patch list. On the narrow P4 project the top
latency stayed 675391 cycles (results/opt_v2/p5_indexloop.json). H1 is false
for this baseline; the top is already the conv1b pixel x RF floor.
"""
import sys
from pathlib import Path

NEEDLE = '''IndexLoop:
    for (int ir = 0; ir < rufactor; ir++) {
        outidx[ir] = outstep;'''

INSERT = '''IndexLoop:
    for (int ir = 0; ir < rufactor; ir++) {
        // P5: IndexLoop was left unpipelined in hls4ml 1.3, so rf_gt_nin_rem0
        // pays rufactor extra cycles per pixel. II=1 is the H1 test.
        #pragma HLS PIPELINE II=1
        outidx[ir] = outstep;'''


def patch_text(text: str) -> str:
    start = text.find('dense_resource_rf_gt_nin_rem0')
    if start < 0:
        raise SystemExit('function dense_resource_rf_gt_nin_rem0 not found')
    # next function or end
    nxt = text.find('\ndense_resource_', start + 10)
    end = nxt if nxt > 0 else len(text)
    body = text[start:end]
    if '#pragma HLS PIPELINE II=1' in body and 'IndexLoop' in body:
        print('already patched')
        return text
    if NEEDLE not in body:
        raise SystemExit('IndexLoop shape does not match the expected hls4ml 1.3 text')
    body = body.replace(NEEDLE, INSERT, 1)
    return text[:start] + body + text[end:]


def main():
    if len(sys.argv) != 2:
        raise SystemExit('usage: patch_hls_indexloop.py <nnet_dense_resource.h>')
    path = Path(sys.argv[1])
    path.write_text(patch_text(path.read_text(encoding='utf-8')), encoding='utf-8')
    print('patched', path)
    return 0


if __name__ == '__main__':
    sys.exit(main())
