#!/usr/bin/env python3
"""Fail fast if csim GAP output is all-zero (precision underflow symptom)."""
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TB = REPO / 'notebooks' / 'hls4ml_prj' / 'tb_data' / 'csim_results.log'
OUT_DIM = int(os.environ.get('OUT_DIM', '24'))


def main() -> int:
    if not TB.is_file():
        print('ERROR: missing %s' % TB, file=sys.stderr)
        return 1
    lines = TB.read_text(encoding='utf-8').strip().splitlines()
    if not lines:
        print('ERROR: empty csim_results.log', file=sys.stderr)
        return 1
    vals = [float(x) for x in lines[0].split()[:OUT_DIM]]
    nonzero = sum(1 for v in vals if abs(v) > 1e-6)
    max_abs = max(abs(v) for v in vals)
    report = {
        'sample0_nonzero_count': nonzero,
        'sample0_max_abs': max_abs,
        'all_zero': nonzero == 0,
    }
    print(json.dumps(report, indent=2))
    if nonzero == 0:
        print('ERROR: csim sample0 all-zero — conv precision likely too narrow', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
