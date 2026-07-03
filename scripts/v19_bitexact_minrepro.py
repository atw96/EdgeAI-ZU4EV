#!/usr/bin/env python3
"""Phase B-1: minimal official QKeras bit_exact repro (no global pop Precision)."""
import json
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT_JSON = REPO / 'results' / 'v19_bitexact_minrepro.json'
TMP = REPO / 'notebooks' / 'hls4ml_prj_v19_bitexact_minrepro_tmp'

sys.path.insert(0, str(REPO / 'scripts'))
from v19_bitexact_probe import _firmware_layer_ops, _judge, _parse_defines, _walk_graph  # noqa: E402
from v19_hls_config_common import build_hls_config  # noqa: E402


def build_tiny_qkeras_model():
    from qkeras import QActivation, QConv2D, QDense, quantized_bits, quantized_relu
    from tensorflow import keras
    from tensorflow.keras import layers

    k_q = quantized_bits(6, 0, alpha='auto_po2')
    b_q = quantized_bits(6, 2, alpha='auto_po2')
    inp_q = quantized_bits(6, 0, alpha='auto_po2')
    act_q = quantized_relu(6, 0)

    inp = keras.Input((8, 8, 3), name='input_image')
    x = QActivation(inp_q, name='input_qact')(inp)
    x = QConv2D(8, 3, padding='same', use_bias=False, kernel_quantizer=k_q, bias_quantizer=b_q, name='conv1')(x)
    x = layers.BatchNormalization(name='bn_conv1')(x)
    x = QActivation(act_q, name='relu_conv1')(x)
    x = layers.GlobalAveragePooling2D(name='gap')(x)
    out = QDense(4, kernel_quantizer=k_q, bias_quantizer=b_q, name='predictions')(x)
    return keras.Model(inp, out, name='tiny_qkeras_bitexact')


def main() -> int:
    import hls4ml

    model = build_tiny_qkeras_model()
    keras_names = [l.name for l in model.layers]
    print('tiny keras layers:', keras_names)

    hls_config = build_hls_config(model, trace=False)
    print('hls4ml', hls4ml.__version__)
    print('bit_exact:', hls_config.get('BackendConfig'))
    print('model precision kept:', 'Precision' in hls_config.get('Model', {}))

    if TMP.exists():
        shutil.rmtree(TMP, ignore_errors=True)

    hls_model = hls4ml.converters.convert_from_keras_model(
        model,
        hls_config=hls_config,
        output_dir=str(TMP),
        backend='Vivado',
        io_type='io_stream',
        part='xczu4ev-sfvc784-1-i',
        clock_period=5,
    )
    hls_model.compile()

    rows, fpq_count = _walk_graph(hls_model)
    defines = _parse_defines(TMP / 'firmware' / 'defines.h')
    fw_ops = _firmware_layer_ops(TMP)
    judge = _judge(rows, fpq_count, fw_ops, keras_names)

    relu_row = next((r for r in rows if r.get('name') == 'relu_conv1'), None)
    report = {
        'route': 'bitexact_minrepro_phase_b1',
        'hls4ml_version': hls4ml.__version__,
        'config_mode': 'standard_no_pop_precision',
        'keras_layer_names': keras_names,
        'relu_conv1': relu_row,
        'defines': {k: defines[k] for k in defines if 'relu' in k or 'input' in k},
        'firmware_ops': fw_ops,
        'judgment': judge,
        'standard_repro_works': judge['fixed_point_quantizer_count'] > 0 and judge['relu_wide_16_6_count'] == 0,
    }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report['judgment'], indent=2))
    print('standard_repro_works:', report['standard_repro_works'])
    print('written:', OUT_JSON)
    return 0


if __name__ == '__main__':
    sys.exit(main())
