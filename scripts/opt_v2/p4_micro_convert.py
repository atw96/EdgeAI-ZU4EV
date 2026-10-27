#!/usr/bin/env python3
"""P4 stock single-layer projects, plus a patched copy of each.

Stock: hls4ml 1.3 defaults, io_stream, Resource, 5 ns, xczu4ev.
Patched: the conv_stream complete->cyclic factor-4 rewrite used by the full net.
Does not touch notebooks/hls4ml_prj.
"""
import os
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / 'results' / 'opt_v2' / 'p4_micro'
sys.path.insert(0, str(REPO / 'scripts'))

CASES = [
    ('c3_rf27', (32, 32, 3), 16, 27),
    ('c3_rf108', (32, 32, 3), 16, 108),
    ('c16_rf144', (32, 32, 16), 16, 144),
    ('c16_rf576', (32, 32, 16), 16, 576),
]


def _apply_conv_patch(prj: Path) -> None:
    from patch_hls_conv_stream import REPLACEMENTS
    header = prj / 'firmware' / 'nnet_utils' / 'nnet_conv_stream.h'
    text = header.read_text(encoding='utf-8')
    for old, new, label in REPLACEMENTS:
        n = text.count(old)
        if n == 0:
            print('WARN', prj.name, 'missing', label)
            continue
        text = text.replace(old, new)
        print('patched', prj.name, label, n)
    header.write_text(text, encoding='utf-8')


def _one(name, shape, filters, rf, patched):
    import hls4ml
    from tensorflow.keras.layers import Conv2D, Input
    from tensorflow.keras.models import Model

    tag = name + ('_patched' if patched else '_stock')
    dest = OUT / tag
    if (dest / 'firmware' / 'nnet_utils' / 'nnet_conv_stream.h').is_file():
        print('keep', dest)
        return
    if dest.exists():
        shutil.rmtree(dest)
    inp = Input(shape=shape, name='img')
    out = Conv2D(filters, (3, 3), padding='same', name='conv')(inp)
    model = Model(inp, out)
    cfg = hls4ml.utils.config_from_keras_model(model, granularity='name')
    cfg['Model']['ReuseFactor'] = rf
    cfg['Model']['Strategy'] = 'Resource'
    cfg['Model']['Precision'] = 'ap_fixed<16,6>'
    cfg['LayerName']['conv']['ReuseFactor'] = rf
    cfg['LayerName']['conv']['Strategy'] = 'Resource'
    print('convert', tag, 'hls4ml', hls4ml.__version__)
    hls_model = hls4ml.converters.convert_from_keras_model(
        model,
        hls_config=cfg,
        output_dir=str(dest),
        backend='Vivado',
        io_type='io_stream',
        part='xczu4ev-sfvc784-1-i',
        clock_period=5,
    )
    hls_model.write()
    if patched:
        _apply_conv_patch(dest)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for name, shape, filters, rf in CASES:
        _one(name, shape, filters, rf, patched=False)
        _one(name, shape, filters, rf, patched=True)
    print('P4 convert done', OUT)
    return 0


if __name__ == '__main__':
    sys.exit(main())
