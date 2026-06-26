#!/usr/bin/env python3
"""GAP-only hls4ml 1.x convert: bit_exact=True, model must include trained input_qact."""
import json
import os
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
HLS_OUT = REPO / 'notebooks' / 'hls4ml_prj'
MODEL_H5 = REPO / 'notebooks' / 'model_int8_qkeras.h5'

RF_PER_LAYER = {
    'conv1a': 432,
    'conv1b': 2304,
    'conv2a': 2880,
    'conv2b': 3600,
    'conv3a': 4320,
    'conv3b': 5184,
    'predictions': 240,
}


def load_full_model():
    import tensorflow as tf
    from qkeras import QActivation, QConv2D, QDense, quantized_bits, quantized_relu

    custom = {
        'QConv2D': QConv2D,
        'QDense': QDense,
        'QActivation': QActivation,
        'quantized_bits': quantized_bits,
        'quantized_relu': quantized_relu,
    }
    return tf.keras.models.load_model(str(MODEL_H5), custom_objects=custom, compile=False)


def load_gap_model():
    import tensorflow as tf

    model = load_full_model()
    if not any(l.name == 'input_qact' for l in model.layers):
        print(
            'ERROR: model_int8_qkeras.h5 missing input_qact layer.\n'
            'Run: python3 scripts/v19_qat_input_qact_finetune.py',
            file=sys.stderr,
        )
        sys.exit(1)
    gap = tf.keras.Model(model.input, model.get_layer('gap').output, name='gaponly')
    print('GAP model layers (head):', [l.name for l in gap.layers[:5]])
    return gap


def configure_rounding_saturation():
    import hls4ml

    try:
        opt = hls4ml.model.optimizer.get_optimizer('output_rounding_saturation_mode')
        opt.configure(
            layers=['QActivation', 'Activation'],
            rounding_mode='AP_RND',
            saturation_mode='AP_SAT',
        )
        print('Configured output_rounding_saturation_mode')
    except Exception as exc:
        print('Note: rounding/saturation configure skipped:', exc)


def build_hls_config(model):
    import hls4ml

    # model granularity avoids per-layer 'auto' that conflicts with bit_exact pass
    cfg = hls4ml.utils.config_from_keras_model(model, granularity='model')
    cfg.setdefault('Backend', 'Vivado')
    cfg.setdefault('BackendConfig', {})['bit_exact'] = True
    cfg['ClockPeriod'] = cfg.get('ClockPeriod', 5)
    cfg['Part'] = cfg.get('Part', 'xczu4ev-sfvc784-1-i')
    cfg['IOType'] = cfg.get('IOType', 'io_stream')

    cfg['Model'].pop('Precision', None)
    cfg['Model']['ReuseFactor'] = 288
    cfg['Model']['Strategy'] = 'Resource'
    cfg['Model']['FifoDepth'] = 2
    cfg['Model']['BramFactor'] = 1000000
    cfg.setdefault('LayerName', {})

    for layer in model.layers:
        lname = layer.name
        low = lname.lower()
        if hasattr(layer, 'kernel') and lname in RF_PER_LAYER:
            cfg['LayerName'].setdefault(lname, {})
            cfg['LayerName'][lname].pop('Precision', None)
            cfg['LayerName'][lname]['ReuseFactor'] = RF_PER_LAYER[lname]
            if 'conv' in low or 'predictions' in low:
                cfg['LayerName'][lname]['Strategy'] = 'Resource'
        elif lname == 'gap':
            cfg['LayerName'].setdefault(lname, {})
            cfg['LayerName'][lname].pop('Precision', None)
            cfg['LayerName'][lname]['Strategy'] = 'Resource'

    for lcfg in cfg.get('LayerName', {}).values():
        lcfg.pop('Precision', None)

    return cfg


def backup_hls_out():
    if not HLS_OUT.exists():
        return
    tag = os.environ.get('BAK_TAG', 'route1')
    bak = HLS_OUT.parent / ('hls4ml_prj.bak_bitexact_%s' % tag)
    if bak.exists():
        shutil.rmtree(bak, ignore_errors=True)
    HLS_OUT.rename(bak)
    print('backed up prior prj ->', bak)


def main():
    import hls4ml

    os.environ.setdefault('GAP_ONLY', '1')
    configure_rounding_saturation()
    gap = load_gap_model()
    hls_config = build_hls_config(gap)

    print('hls4ml', hls4ml.__version__)
    print('bit_exact BackendConfig:', hls_config.get('BackendConfig'))

    backup_hls_out()

    hls_model = hls4ml.converters.convert_from_keras_model(
        gap,
        hls_config=hls_config,
        output_dir=str(HLS_OUT),
        backend='Vivado',
        io_type='io_stream',
        part='xczu4ev-sfvc784-1-i',
        clock_period=5,
    )
    hls_model.compile()
    hls_model.write()

    defines = HLS_OUT / 'firmware' / 'defines.h'
    if defines.exists():
        for line in defines.read_text(encoding='utf-8').splitlines():
            if 'result_t' in line or ('input' in line and 'typedef' in line):
                print('defines:', line.strip())

    summary = {
        'route': 'bitexact_route1',
        'hls4ml_version': hls4ml.__version__,
        'bit_exact': True,
        'model_h5': str(MODEL_H5),
        'has_input_qact': True,
        'hls_out': str(HLS_OUT),
    }
    out_json = REPO / 'results' / 'v19_bitexact_convert.json'
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print('written:', out_json)
    return 0


if __name__ == '__main__':
    sys.exit(main())
