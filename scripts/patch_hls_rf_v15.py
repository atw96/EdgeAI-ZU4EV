#!/usr/bin/env python3
"""v15: full-serialize conv/mult RF (1 parallel mult lane per layer)."""
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PARAMS = REPO / 'notebooks' / 'hls4ml_prj' / 'firmware' / 'parameters.h'

# RF = kernel_size * n_chan * n_filt (conv) or n_in * n_out (pointwise mult).
CONV_RF = {
    'config2': 432,      # 3*3*3*16
    'config6': 2304,     # 3*3*16*16
    'config11': 2880,    # 3*3*16*20
    'config15': 3600,    # 3*3*20*20
    'config20': 4320,    # 3*3*20*24
    'config24': 5184,    # 3*3*24*24
}

MULT_RF = {
    'config2_mult': 432,     # 27*16
    'config6_mult': 2304,    # 144*16
    'config11_mult': 2880,   # 144*20
    'config15_mult': 3600,   # 180*20
    'config20_mult': 4320,   # 180*24
    'config24_mult': 5184,   # 216*24
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
            print('patched %s reuse_factor -> %d (1x mult lane)' % (cfg, rf))
            changed = True
    for cfg, rf in MULT_RF.items():
        text, n = _patch_rf(text, cfg, rf, 'nnet::dense_config')
        if n:
            print('patched %s reuse_factor -> %d (1x mult lane)' % (cfg, rf))
            changed = True
    if changed:
        PARAMS.write_text(text, encoding='utf-8')
    print('rf_v15 changed=%s' % changed)
    return 0


if __name__ == '__main__':
    sys.exit(main())
