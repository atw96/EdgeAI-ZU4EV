#!/usr/bin/env python3
"""Write tb_input_features.dat for N bench samples (int16/1024 -> float line)."""
import os
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
# CSIM_NPZ selects the sample file. P1 uses the first 1000 CIFAR-10 test images.
NPZ = Path(os.environ.get('CSIM_NPZ', str(REPO / 'deploy' / 'cifar10_bench.npz')))
TB = REPO / 'notebooks' / 'hls4ml_prj' / 'tb_data'
META = REPO / 'notebooks' / 'hls4ml_prj' / 'axi_wrapper_meta.json'
N = int(os.environ.get('N_GAP_COMPARE', '10'))
IN_SCALE = int(os.environ.get('IN_FIXED_SCALE', '1024'))


def resolve_input_scale():
    return int(os.environ.get('IN_FIXED_SCALE', str(IN_SCALE)))


def main():
    in_scale = resolve_input_scale()
    data = np.load(NPZ, allow_pickle=True)
    n = min(N, len(data['payloads']))
    TB.mkdir(parents=True, exist_ok=True)
    in_path = TB / 'tb_input_features.dat'
    out_path = TB / 'tb_output_predictions.dat'
    with in_path.open('w', encoding='utf-8') as inf, out_path.open('w', encoding='utf-8') as outf:
        for i in range(n):
            raw = bytes(data['payloads'][i])
            x = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / float(in_scale)
            line = ' '.join(str(float(v)) for v in x)
            inf.write(line + '\n')
            outf.write(line + '\n')
            if (i + 1) % 500 == 0:
                print('prepared %d/%d' % (i + 1, n), flush=True)
    print('Wrote %d lines to %s (in_scale=%d)' % (n, in_path, in_scale))
    return 0


if __name__ == '__main__':
    sys.exit(main())
