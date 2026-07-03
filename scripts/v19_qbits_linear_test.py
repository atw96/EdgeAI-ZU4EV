#!/usr/bin/env python3
"""Quick test: quantized_bits(6,2) activations -> nnet::linear in firmware."""
import os
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TMP = REPO / 'notebooks' / 'hls4ml_prj_qbits_test'

sys.path.insert(0, str(REPO / 'scripts'))
from v19_hls_config_common import build_hls_config, configure_rounding_saturation  # noqa: E402


def build_gap_qbits():
    import tensorflow as tf
    from qkeras import QActivation, QConv2D, quantized_bits
    from tensorflow.keras import layers

    k_q = quantized_bits(6, 0, alpha='auto_po2')
    b_q = quantized_bits(6, 2, alpha='auto_po2')
    a_q = quantized_bits(6, 2, alpha='auto_po2')
    inp_q = quantized_bits(6, 0, alpha='auto_po2')

    def block(x, f, p):
        for s in ('a', 'b'):
            n = '%s%s' % (p, s)
            x = QConv2D(
                f, 3, padding='same', use_bias=False,
                kernel_quantizer=k_q, bias_quantizer=b_q, name=n,
            )(x)
            x = layers.BatchNormalization(name='bn_%s' % n)(x)
            x = QActivation(a_q, name='relu_%s' % n)(x)
        return x

    inp = tf.keras.Input((32, 32, 3), name='input_image')
    x = QActivation(inp_q, name='input_qact')(inp)
    x = block(x, 16, 'conv1')
    x = layers.MaxPooling2D(2, name='pool1')(x)
    x = block(x, 20, 'conv2')
    x = layers.MaxPooling2D(2, name='pool2')(x)
    x = block(x, 24, 'conv3')
    x = layers.GlobalAveragePooling2D(name='gap')(x)
    return tf.keras.Model(inp, x)


def main():
    import hls4ml

    os.environ.setdefault('GAP_ONLY', '1')
    gap = build_gap_qbits()
    gap.load_weights(str(REPO / 'notebooks' / 'model_int8_qkeras.h5'), by_name=True, skip_mismatch=True)

    if TMP.exists():
        shutil.rmtree(TMP, ignore_errors=True)

    configure_rounding_saturation(gap)
    cfg = build_hls_config(gap)
    hls_model = hls4ml.converters.convert_from_keras_model(
        gap, hls_config=cfg, output_dir=str(TMP),
        backend='Vivado', io_type='io_stream',
        part='xczu4ev-sfvc784-1-i', clock_period=5,
    )
    hls_model.compile()

    cpp = TMP / 'firmware' / 'myproject.cpp'
    for line in cpp.read_text(encoding='utf-8').splitlines():
        if 'nnet::' in line and '//' in line and any(k in line for k in ('relu', 'input_qact', 'linear')):
            print(line.strip())
    return 0


if __name__ == '__main__':
    sys.exit(main())
