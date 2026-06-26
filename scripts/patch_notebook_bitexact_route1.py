#!/usr/bin/env python3
"""Route 1: bit_exact=True, RF/Strategy only — strip all manual PREC + Plan B patches."""
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
NB = REPO / 'notebooks' / 'cifar10_hls4ml_synthesis.ipynb'
MARKER = 'ROUTE1_BITEXACT = True'

ROUTE1_BLOCK = '''
# ── Step 2: Global defaults (Route 1 — no manual Model Precision) ──
hls_config['Model']['ReuseFactor']  = 288
hls_config['Model']['Strategy']     = 'Resource'
hls_config['Model']['FifoDepth']    = 2
hls_config['Model']['BramFactor']   = 1000000

ROUTE1_BITEXACT = True
hls_config.setdefault('BackendConfig', {})['bit_exact'] = True
print('Route 1: BackendConfig bit_exact=True (QKeras auto precision, no PREC patches)')

# Step 3-5: ReuseFactor + Strategy only (precision from quantizers via bit_exact)
for layer in model.layers:
    lname = layer.name
    low = lname.lower()
    if hasattr(layer, 'kernel') and lname in RF_PER_LAYER:
        hls_config['LayerName'].setdefault(lname, {})
        hls_config['LayerName'][lname]['ReuseFactor'] = RF_PER_LAYER[lname]
        if 'conv' in low or 'dense' in low or 'predictions' in low:
            hls_config['LayerName'][lname]['Strategy'] = 'Resource'
    elif lname == 'gap':
        hls_config['LayerName'].setdefault(lname, {})
        hls_config['LayerName'][lname]['Strategy'] = 'Resource'

for lname in ('predictions_logits',):
    if lname in hls_config.get('LayerName', {}):
        hls_config['LayerName'][lname]['Strategy'] = 'Latency'
        hls_config['LayerName'][lname]['ReuseFactor'] = 1
'''


def strip_plan_b(src: str) -> tuple:
    changed = 0
    patterns = [
        r'\n# Step 6: conv1a/conv1b targeted widen.*?print\(\'Step 6: conv1a/conv1b overrides applied\'\)\n',
        r'\nPREC_CONV1A = \{.*?\n\}\n',
        r'\nPREC_CONV1B = \{.*?\n\}\n',
        r'\nPREC_BN1AB = \{.*?\n\}\n',
        r"\nhls_config\['LayerName'\]\.setdefault\('input_image', \{\}\)\n"
        r"hls_config\['LayerName'\]\['input_image'\]\['Precision'\] = \{'result': 'ap_fixed<16,6>'\}\n",
        r"\nhls_config\['BackendConfig'\]\['bit_exact'\] = False\n",
    ]
    for pat in patterns:
        new_src, n = re.subn(pat, '\n', src, count=1, flags=re.S)
        if n:
            src = new_src
            changed += n
    return src, changed


def main() -> int:
    nb = json.loads(NB.read_text(encoding='utf-8'))
    src = ''.join(nb['cells'][6]['source'])

    if MARKER in src:
        print('Notebook cell 6 already Route 1 — no change')
        return 0

    src, n_planb = strip_plan_b(src)

    pat = re.compile(
        r'# ── Step 2: Global defaults.*?'
        r"(?=print\('HLS Configuration:'\))",
        re.S,
    )
    new_src, n = pat.subn(ROUTE1_BLOCK + '\n', src, count=1)
    if n != 1:
        print('ERROR: Step 2 anchor not found in cell 6', file=sys.stderr)
        return 1

    nb['cells'][6]['source'] = [new_src]
    NB.write_text(json.dumps(nb, indent=1), encoding='utf-8')
    print('Patched %s: Route 1 bit_exact (removed manual PREC, plan_b=%d)' % (NB, n_planb))
    return 0


if __name__ == '__main__':
    sys.exit(main())
