#!/usr/bin/env python3
"""Compare two hls4ml exports. Weights and defines.h must be identical.

parameters.h may differ only on reuse_factor / multiplier_limit / n_zeros lines.
Exit 1 when the export itself is not reproducible. Does not overwrite its JSON.
"""
import filecmp
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RF_LINE = re.compile(r'reuse_factor|multiplier_limit|n_zeros|DenseResource_rf_')


def _strip_rf(text):
    return '\n'.join(line for line in text.splitlines() if not RF_LINE.search(line))


def main():
    if len(sys.argv) != 4:
        print('usage: p1_static_diff.py <dir_a> <dir_b> <out_json>', file=sys.stderr)
        return 2
    a = Path(sys.argv[1])
    b = Path(sys.argv[2])
    out = Path(sys.argv[3])
    if out.exists():
        print('ERROR: refuse to overwrite %s' % out, file=sys.stderr)
        return 1
    weight_files = sorted(p.name for p in (a / 'weights').iterdir() if p.is_file())
    weight_diff = []
    for name in weight_files:
        left = a / 'weights' / name
        right = b / 'weights' / name
        if not right.is_file() or not filecmp.cmp(left, right, shallow=False):
            weight_diff.append(name)
    defines_same = filecmp.cmp(a / 'defines.h', b / 'defines.h', shallow=False)
    params_same = _strip_rf((a / 'parameters.h').read_text(encoding='utf-8')) == _strip_rf(
        (b / 'parameters.h').read_text(encoding='utf-8')
    )
    ok = not weight_diff and defines_same and params_same
    doc = {
        'dir_a': str(a),
        'dir_b': str(b),
        'weight_files': len(weight_files),
        'weight_files_differ': weight_diff,
        'defines_identical': defines_same,
        'parameters_identical_except_rf': params_same,
        'pass': ok,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2), encoding='utf-8')
    print(json.dumps(doc, indent=2))
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
