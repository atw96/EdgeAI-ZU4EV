#!/usr/bin/env python3
"""Raise ReuseFactor on conv + pointwise mult layers to cut LUT (v8/v9)."""
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PARAMS = REPO / 'notebooks' / 'hls4ml_prj' / 'firmware' / 'parameters.h'

# 3x3 conv: RF divides kernel_size*n_chan*n_filt. Target ~4 parallel mults/layer.
CONV_RF = {
    'config2': 432,
    'config6': 576,
    'config11': 576,
    'config15': 720,
    'config20': 864,
    'config24': 1296,
}

# 1x1 pointwise (dense_config *_mult): RF divides n_in*n_out.
MULT_RF = {
    'config2_mult': 432,
    'config6_mult': 576,
    'config11_mult': 720,
    'config15_mult': 900,
    'config20_mult': 1080,
    'config24_mult': 1296,
}


def _patch_rf(text: str, cfg: str, rf: int, struct_pat: str) -> tuple:
    pat = (
        r'(struct %s : %s \{.*?'
        r'static const unsigned reuse_factor = )\d+(;)' % (cfg, struct_pat)
    )
    new_text, n = re.subn(pat, r'\g<1>%d\2' % rf, text, count=1, flags=re.S)
    if n == 0:
        print('WARN: could not patch %s reuse_factor' % cfg, file=sys.stderr)
        return text, False
    print('patched %s reuse_factor -> %d' % (cfg, rf))
    return new_text, True


def patch_parameters() -> bool:
    if not PARAMS.exists():
        print('ERROR: missing %s' % PARAMS, file=sys.stderr)
        return False
    text = PARAMS.read_text(encoding='utf-8')
    changed = False
    for cfg, rf in CONV_RF.items():
        text, ok = _patch_rf(text, cfg, rf, 'nnet::conv2d_config')
        changed = changed or ok
    for cfg, rf in MULT_RF.items():
        text, ok = _patch_rf(text, cfg, rf, 'nnet::dense_config')
        changed = changed or ok
    if changed:
        PARAMS.write_text(text, encoding='utf-8')
    return changed


def main() -> int:
    ok = patch_parameters()
    print('parameters_patched=%s' % ok)
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
