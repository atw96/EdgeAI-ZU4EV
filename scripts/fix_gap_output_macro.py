#!/usr/bin/env python3
"""Fix output-size parsing when GAP-only export has N_FILT_* but no N_LAYER_*."""
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def patch_axi_wrapper():
    p = REPO / 'scripts/patch_axi_wrapper.py'
    text = p.read_text(encoding='utf-8')
    if 'N_OUT_%d' in text:
        return False
    old = """def parse_output_macro(text):
    matches = re.findall(r'#define\\s+(N_LAYER_\\d+)\\s+(\\d+)', text)
    if not matches:
        raise RuntimeError('no N_LAYER_* in defines.h')
    name, val = matches[-1]
    return name, int(val)"""
    new = """def parse_output_macro(text):
    matches = re.findall(r'#define\\s+(N_LAYER_\\d+)\\s+(\\d+)', text)
    if matches:
        name, val = matches[-1]
        return name, int(val)
    m = re.search(
        r'typedef nnet::array<ap_fixed<\\d+,\\s*\\d+>,\\s*(\\d+)\\*1>\\s+result_t',
        text,
    )
    if m:
        n = int(m.group(1))
        for fname, fval in reversed(
            re.findall(r'#define\\s+(N_FILT_\\d+)\\s+(\\d+)', text)
        ):
            if int(fval) == n:
                return fname, n
        return ('N_OUT_%d' % n, n)
    raise RuntimeError('no N_LAYER_* or result_t in defines.h')"""
    if old not in text:
        raise RuntimeError('patch_axi_wrapper anchor missing')
    p.write_text(text.replace(old, new), encoding='utf-8')
    return True


def patch_notebook():
    nb_path = REPO / 'notebooks/cifar10_hls4ml_synthesis.ipynb'
    nb = json.loads(nb_path.read_text(encoding='utf-8'))
    marker = 'return f\'N_OUT_{n}\''
    for cell in nb['cells']:
        if cell['cell_type'] != 'code':
            continue
        src = ''.join(cell['source'])
        if 'def parse_output_layer_macro' not in src:
            continue
        if marker in src:
            return False
        old = "    if not matches:\n        raise RuntimeError(f'No N_LAYER_* macro in {defines_h_path}')"
        new = (
            "    if not matches:\n"
            "        m = re.search(\n"
            "            r'typedef nnet::array<ap_fixed<\\d+,\\s*\\d+>,\\s*(\\d+)\\*1>\\s+result_t',\n"
            "            text,\n"
            "        )\n"
            "        if m:\n"
            "            n = int(m.group(1))\n"
            "            for fname, fval in reversed(re.findall(r'#define\\s+(N_FILT_\\d+)\\s+(\\d+)', text)):\n"
            "                if int(fval) == n:\n"
            "                    return fname\n"
            "            return f'N_OUT_{n}'\n"
            "        raise RuntimeError(f'No N_LAYER_* macro in {defines_h_path}')"
        )
        if old not in src:
            raise RuntimeError('notebook anchor missing')
        cell['source'] = [src.replace(old, new, 1)]
        nb_path.write_text(json.dumps(nb, indent=1), encoding='utf-8')
        return True
    raise RuntimeError('parse_output_layer_macro cell not found')


def main():
    a = patch_axi_wrapper()
    n = patch_notebook()
    print('axi_wrapper=%s notebook=%s' % (a, n))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
