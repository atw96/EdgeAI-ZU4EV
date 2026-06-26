#!/usr/bin/env python3
"""Execute notebook cells that regenerate hls4ml_prj (config + convert + wrapper)."""
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
NB = REPO / 'notebooks' / 'cifar10_hls4ml_synthesis.ipynb'
# 0-based: imports(2), load model(4), hls config(6), fifo tools(8), convert(10).
CELL_INDICES = (2, 4, 6, 8, 10)


def main():
    nb = json.loads(NB.read_text(encoding='utf-8'))
    os.chdir(REPO / 'notebooks')
    g = {'__name__': '__main__', '__file__': str(NB)}
    for idx in CELL_INDICES:
        cell = nb['cells'][idx]
        if cell['cell_type'] != 'code':
            print('ERROR: cell %d is not code' % idx, file=sys.stderr)
            return 1
        src = ''.join(cell['source'])
        print('=== executing notebook cell %d ===' % idx)
        exec(compile(src, str(NB) + ':%d' % idx, 'exec'), g)
    import subprocess
    subprocess.check_call([sys.executable, str(REPO / 'scripts' / 'patch_axi_wrapper.py')])
    defines = REPO / 'notebooks' / 'hls4ml_prj' / 'firmware' / 'defines.h'
    if defines.exists():
        for line in defines.read_text(encoding='utf-8').splitlines():
            if 'result_t' in line and 'typedef' in line:
                print('defines.h:', line.strip())
    return 0


if __name__ == '__main__':
    sys.exit(main())
