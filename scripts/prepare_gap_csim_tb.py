#!/usr/bin/env python3
"""Write tb_input_features.dat for N bench samples (int16/1024 -> float line)."""
import os
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
NPZ = REPO / 'deploy' / 'cifar10_bench.npz'
TB = REPO / 'notebooks' / 'hls4ml_prj' / 'tb_data'
N = int(os.environ.get('N_GAP_COMPARE', '10'))
IN_SCALE = int(os.environ.get('IN_FIXED_SCALE', '1024'))


def main():
    data = np.load(NPZ, allow_pickle=True)
    n = min(N, len(data['payloads']))
    TB.mkdir(parents=True, exist_ok=True)
    in_lines = []
    for i in range(n):
        raw = bytes(data['payloads'][i])
        x = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / float(IN_SCALE)
        in_lines.append(' '.join(str(float(v)) for v in x))
    (TB / 'tb_input_features.dat').write_text('\n'.join(in_lines) + '\n', encoding='utf-8')
  # predictions file: same line count (content ignored by tb)
    (TB / 'tb_output_predictions.dat').write_text('\n'.join(in_lines) + '\n', encoding='utf-8')
    print('Wrote %d lines to %s' % (n, TB / 'tb_input_features.dat'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
