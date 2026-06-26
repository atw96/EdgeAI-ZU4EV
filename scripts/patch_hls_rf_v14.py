#!/usr/bin/env python3
"""v14: raise conv/mult RF (~2x v13) to cut LUT toward ~80K budget."""
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PARAMS = REPO / 'notebooks' / 'hls4ml_prj' / 'firmware' / 'parameters.h'

# Target ~2 parallel mults/layer (was ~4 in v13).
CONV_RF = {
    'config2': 864,
    'config6': 1152,
    'config11': 1152,
    'config15': 1440,
    'config20': 1728,
    'config24': 2592,
}

MULT_RF = {
    'config2_mult': 864,
    'config6_mult': 1152,
    'config11_mult': 1440,
    'config15_mult': 1800,
    'config20_mult': 2160,
    'config24_mult': 2592,
}


def _patch_rf(text, cfg, rf, struct_pat):
    pat = (
        r'(struct %s : %s \{.*?'
        r'static const unsigned reuse_factor = )\d+(;)' % (cfg, struct_pat)
    )
    return re.subn(pat, r'\g<1>%d\2' % rf, text, count=1, flags=re.S)


def main() -> int:
    if not PARAMS.is_file():
        print('ERROR: missing %s' % PARAMS, file=sys.stderr)
        return 1
    text = PARAMS.read_text(encoding='utf-8')
    changed = False
    for cfg, rf in CONV_RF.items():
        text, n = _patch_rf(text, cfg, rf, 'nnet::conv2d_config')
        if n:
            print('patched %s reuse_factor -> %d' % (cfg, rf))
            changed = True
    for cfg, rf in MULT_RF.items():
        text, n = _patch_rf(text, cfg, rf, 'nnet::dense_config')
        if n:
            print('patched %s reuse_factor -> %d' % (cfg, rf))
            changed = True
    if changed:
        PARAMS.write_text(text, encoding='utf-8')
    print('rf_v14 changed=%s' % changed)
    return 0


if __name__ == '__main__':
    sys.exit(main())
