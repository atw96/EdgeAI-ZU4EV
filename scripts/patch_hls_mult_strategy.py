#!/usr/bin/env python3
"""v13: pointwise mult layers use dense_resource (fewer HLS clones, same math)."""
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PARAMS = REPO / 'notebooks' / 'hls4ml_prj' / 'firmware' / 'parameters.h'

MULT_CFGS = [
    'config2_mult', 'config6_mult', 'config11_mult', 'config15_mult',
    'config20_mult', 'config24_mult',
]


def main() -> int:
    if not PARAMS.is_file():
        print('ERROR: missing %s' % PARAMS, file=sys.stderr)
        return 1
    text = PARAMS.read_text(encoding='utf-8')
    changed = False
    for cfg in MULT_CFGS:
        pat = (
            r'(struct %s : nnet::dense_config \{.*?'
            r'static const unsigned strategy = )nnet::latency(;)' % cfg
        )
        new_text, n = re.subn(
            pat, r'\g<1>nnet::resource\2', text, count=1, flags=re.S
        )
        if n:
            print('patched %s strategy latency -> resource' % cfg)
            text = new_text
            changed = True
        elif re.search(
            r'struct %s : nnet::dense_config \{.*?strategy = nnet::resource'
            % cfg, text, re.S
        ):
            print('%s already resource' % cfg)
        else:
            print('WARN: could not patch %s strategy' % cfg, file=sys.stderr)
    if changed:
        PARAMS.write_text(text, encoding='utf-8')
    print('mult_strategy changed=%s' % changed)
    return 0


if __name__ == '__main__':
    sys.exit(main())
