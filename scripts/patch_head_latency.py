#!/usr/bin/env python3
"""Strategy step ④: set predictions_logits Strategy=Latency in notebook hls config."""
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
NB = REPO / 'notebooks' / 'cifar10_hls4ml_synthesis.ipynb'
CFG = REPO / 'notebooks' / 'hls4ml_prj' / 'hls4ml_config.yml'


def patch_notebook():
    nb = json.loads(NB.read_text(encoding='utf-8'))
    changed = False
    for cell in nb['cells']:
        if cell['cell_type'] != 'code':
            continue
        src = ''.join(cell['source'])
        if 'predictions_logits' not in src and 'PREC_HEAD' not in src:
            continue
        if "predictions_logits']['Strategy']" in src:
            return False
        new = src
        anchor = "for lname in ('gap', 'predictions', 'predictions_logits'):"
        if anchor in new:
            insert = (
                "\n    if lname == 'predictions_logits':\n"
                "        hls_config['LayerName'][lname]['Strategy'] = 'Latency'\n"
                "        hls_config['LayerName'][lname]['ReuseFactor'] = 1\n"
            )
            new = new.replace(
                "    if lname in RF_PER_LAYER:\n",
                insert + "    if lname in RF_PER_LAYER:\n",
                1,
            )
            cell['source'] = [new]
            NB.write_text(json.dumps(nb, indent=1), encoding='utf-8')
            changed = True
            break
    return changed


def patch_yaml():
    if not CFG.exists():
        return False
    text = CFG.read_text(encoding='utf-8')
    if 'predictions_logits' in text and 'Latency' in text:
        return False
    if 'predictions_logits' not in text:
        text += "\n  predictions_logits:\n    Strategy: Latency\n    ReuseFactor: 1\n"
    else:
        text = re.sub(
            r'(predictions_logits:.*)',
            r'\1\n    Strategy: Latency\n    ReuseFactor: 1',
            text,
            count=1,
        )
    CFG.write_text(text, encoding='utf-8')
    return True


def main():
    n = patch_notebook()
    y = patch_yaml()
    print('notebook_patched=%s yaml_patched=%s' % (n, y))
    if n or y:
        print('Next: python3 scripts/execute_hls_convert_cells.py && run_axi_fix_pipeline')
    return 0


if __name__ == '__main__':
    sys.exit(main())
