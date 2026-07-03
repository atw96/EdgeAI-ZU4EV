#!/usr/bin/env python3
"""Multiply conv2d/mult reuse_factor in parameters.h to cut LUT (post-convert)."""
import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PARAMS = REPO / 'notebooks' / 'hls4ml_prj' / 'firmware' / 'parameters.h'
MULT = int(os.environ.get('HLS_RF_MULTIPLY', '2'))


def patch_struct(text: str, struct_pat: str) -> tuple:
    changed = False

    def repl(m):
        nonlocal changed
        rf = int(m.group(1))
        new_rf = rf * MULT
        changed = True
        return 'reuse_factor = %d' % new_rf

    pat = (
        r'(struct \w+ : %s \{.*?static const unsigned )reuse_factor = (\d+)(;)' % struct_pat
    )
    new_text, n = re.subn(pat, lambda m: '%sreuse_factor = %d%s' % (m.group(1), int(m.group(2)) * MULT, m.group(3)),
                          text, flags=re.S)
    return new_text, changed and n > 0


def main() -> int:
    if not PARAMS.is_file():
        print('ERROR: missing %s' % PARAMS, file=sys.stderr)
        return 1
    text = PARAMS.read_text(encoding='utf-8')
    for struct_pat in ('nnet::conv2d_config', 'nnet::dense_config'):
        text, ok = patch_struct(text, struct_pat)
        if ok:
            print('multiplied %s reuse_factor x%d' % (struct_pat, MULT))
    PARAMS.write_text(text, encoding='utf-8')
    return 0


if __name__ == '__main__':
    sys.exit(main())
