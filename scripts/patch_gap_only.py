#!/usr/bin/env python3
"""Patch notebook for GAP-only HLS export + save Dense weights for PS inference."""
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
NB = REPO / 'notebooks' / 'cifar10_hls4ml_synthesis.ipynb'
DENSE_NPZ = REPO / 'deploy' / 'dense_head.npz'
MODEL_H5 = REPO / 'notebooks' / 'model_int8_qkeras.h5'

GAP_ONLY_MARKER = "os.environ.get('GAP_ONLY', '0') == '1'"


def patch_notebook():
    nb = json.loads(NB.read_text(encoding='utf-8'))
    for cell in nb['cells']:
        if cell['cell_type'] != 'code':
            continue
        src = ''.join(cell['source'])
        if '_dense_lname' not in src or 'model_hls' not in src:
            continue
        if GAP_ONLY_MARKER in src:
            return False
        gap_block = (
            "import os\n"
            "if os.environ.get('GAP_ONLY', '0') == '1':\n"
            "    model_hls = tf.keras.Model(\n"
            "        inputs=model.input,\n"
            "        outputs=model.get_layer('gap').output,\n"
            "        name=model.name + '_gaponly',\n"
            "    )\n"
            "    print('HLS model GAP-only. Output layer: gap')\n"
            "elif _dense_lname is not None:\n"
        )
        old = "if _dense_lname is not None:\n"
        if old not in src:
            print('ERROR: anchor not found in convert cell', file=sys.stderr)
            return False
        cell['source'] = [src.replace(old, gap_block, 1)]
        NB.write_text(json.dumps(nb, indent=1), encoding='utf-8')
        return True


def export_dense_weights():
    import numpy as np
    import tensorflow as tf
    from qkeras import QConv2D, QDense, QActivation, quantized_bits, quantized_relu

    if not MODEL_H5.exists():
        print('ERROR: missing %s' % MODEL_H5, file=sys.stderr)
        return False
    custom_objs = {
        'QConv2D': QConv2D,
        'QDense': QDense,
        'QActivation': QActivation,
        'quantized_bits': quantized_bits,
        'quantized_relu': quantized_relu,
    }
    model = tf.keras.models.load_model(
        str(MODEL_H5), custom_objects=custom_objs, compile=False,
    )
    dense = None
    for lyr in reversed(model.layers):
        if 'predictions' in lyr.name.lower() or isinstance(lyr, tf.keras.layers.Dense):
            dense = lyr
            break
    if dense is None:
        print('ERROR: no Dense layer in model', file=sys.stderr)
        return False
    w, b = dense.get_weights()
    DENSE_NPZ.parent.mkdir(parents=True, exist_ok=True)
    np.savez(DENSE_NPZ, weight=w.astype(np.float32), bias=b.astype(np.float32))
    print('Saved dense head: weight%s bias%s -> %s' % (w.shape, b.shape, DENSE_NPZ))
    return True


def main():
    n = patch_notebook()
    d = export_dense_weights()
    print('notebook_patched=%s dense_exported=%s' % (n, d))
    if n:
        print('Next: GAP_ONLY=1 python3 scripts/execute_hls_convert_cells.py')
    return 0 if d else 1


if __name__ == '__main__':
    sys.exit(main())
