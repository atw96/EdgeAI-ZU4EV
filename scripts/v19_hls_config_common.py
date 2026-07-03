#!/usr/bin/env python3
"""Shared Route 1 hls4ml config + model loading (standard QKeras granularity=name)."""
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MODEL_H5 = REPO / 'notebooks' / 'model_int8_qkeras.h5'

# Lower RF for more parallelism (impl LUT/BRAM headroom; valid hls4ml divisors).
RF_PER_LAYER = {
    'conv1a': 108,
    'conv1b': 576,
    'conv2a': 720,
    'conv2b': 900,
    'conv3a': 1080,
    'conv3b': 1296,
    'predictions': 240,
}

# Non-bit_exact: narrow conv/bn stream types to cut dataflow FIFO BRAM (38/21-bit -> 16-bit).
PREC_CONV_NARROW = {
    'result': 'ap_fixed<16,8,RND_CONV,SAT,0>',
    'weight': 'ap_fixed<6,1,RND_CONV,SAT,0>',
    'bias': 'ap_fixed<6,2,RND_CONV,SAT,0>',
    'accum': 'ap_fixed<16,8,RND_CONV,SAT,0>',
}
PREC_BN_NARROW = {
    'result': 'ap_fixed<16,8,RND_CONV,SAT,0>',
    'scale': 'ap_fixed<16,8,RND_CONV,SAT,0>',
    'bias': 'ap_fixed<16,8,RND_CONV,SAT,0>',
    'accum': 'ap_fixed<16,8,RND_CONV,SAT,0>',
}

QKERAS_CUSTOM = None


def _qkeras_custom():
    global QKERAS_CUSTOM
    if QKERAS_CUSTOM is None:
        from qkeras import QActivation, QConv2D, QDense, quantized_bits, quantized_relu

        QKERAS_CUSTOM = {
            'QConv2D': QConv2D,
            'QDense': QDense,
            'QActivation': QActivation,
            'quantized_bits': quantized_bits,
            'quantized_relu': quantized_relu,
        }
    return QKERAS_CUSTOM


def load_full_model(model_h5=None):
    import tensorflow as tf

    path = Path(model_h5) if model_h5 else MODEL_H5
    return tf.keras.models.load_model(
        str(path), custom_objects=_qkeras_custom(), compile=False,
    )


def load_gap_model(model_h5=None, require_input_qact=True):
    import tensorflow as tf

    model = load_full_model(model_h5)
    if require_input_qact and not any(l.name == 'input_qact' for l in model.layers):
        print(
            'ERROR: model missing input_qact layer.\n'
            'Run: python3 scripts/v19_qat_input_qact_finetune.py',
            file=sys.stderr,
        )
        sys.exit(1)
    return tf.keras.Model(model.input, model.get_layer('gap').output, name='gaponly')


def configure_rounding_saturation(model=None):
    """Only layers with fully resolved precision (input_qact); relu_conv* stay on auto until infer."""
    import hls4ml

    layer_list = ['input_qact']

    try:
        opt = hls4ml.model.optimizer.get_optimizer('output_rounding_saturation_mode')
        opt.configure(
            layers=layer_list,
            rounding_mode='AP_RND',
            saturation_mode='AP_SAT',
        )
        print('Configured output_rounding_saturation_mode for', layer_list)
    except Exception as exc:
        print('Note: rounding/saturation configure skipped:', exc)


def _apply_route1_overrides(cfg, model, trace=False, bit_exact=False):
    """Synthesis overrides — preserve LayerName Precision from QKeras quantizers."""
    cfg.setdefault('Backend', 'Vivado')
    cfg.setdefault('BackendConfig', {})
    cfg['ClockPeriod'] = cfg.get('ClockPeriod', 5)
    cfg['Part'] = cfg.get('Part', 'xczu4ev-sfvc784-1-i')
    cfg['IOType'] = cfg.get('IOType', 'io_stream')

    cfg.setdefault('Model', {})
    cfg['Model']['ReuseFactor'] = 288
    cfg['Model']['Strategy'] = 'Resource'
    cfg['Model']['BramFactor'] = 1000000
    cfg.setdefault('LayerName', {})

    for layer in model.layers:
        lname = layer.name
        low = lname.lower()
        cfg['LayerName'].setdefault(lname, {})
        if trace:
            cfg['LayerName'][lname]['Trace'] = True
        if hasattr(layer, 'kernel') and lname in RF_PER_LAYER:
            cfg['LayerName'][lname]['ReuseFactor'] = RF_PER_LAYER[lname]
            if 'conv' in low or 'predictions' in low:
                cfg['LayerName'][lname]['Strategy'] = 'Resource'
            if not bit_exact and low.startswith('conv') and 'predictions' not in low:
                cfg['LayerName'][lname]['Precision'] = dict(PREC_CONV_NARROW)
        elif low.startswith('bn_conv') and not bit_exact:
            cfg['LayerName'][lname]['Precision'] = dict(PREC_BN_NARROW)
        elif lname == 'gap':
            cfg['LayerName'][lname]['Strategy'] = 'Resource'
            if not bit_exact:
                cfg['LayerName'][lname]['Precision'] = {
                    'result': 'ap_ufixed<12,2,RND_CONV,SAT,0>',
                    'accum': 'ap_ufixed<18,8,RND_CONV,SAT,0>',
                }

    return cfg


def _model_uses_auto_po2(model):
    for layer in model.layers:
        for attr in ('kernel_quantizer', 'bias_quantizer', 'activation'):
            q = getattr(layer, attr, None)
            if q is None:
                continue
            cfg = getattr(q, 'config', None) or {}
            if cfg.get('alpha') == 'auto_po2':
                return True
            qstr = str(q)
            if 'auto_po2' in qstr:
                return True
    return False


def build_hls_config(model, trace=False, bit_exact=False):
    """Standard QKeras config: granularity=name keeps per-layer Precision from quantizers."""
    import hls4ml

    cfg = hls4ml.utils.config_from_keras_model(
        model,
        granularity='name',
        default_precision='fixed<16,6>',
    )
    cfg = _apply_route1_overrides(cfg, model, trace=trace, bit_exact=bit_exact)
    if bit_exact:
        cfg.setdefault('BackendConfig', {})['bit_exact'] = True
        if _model_uses_auto_po2(model):
            cfg['SkipOptimizers'] = ['qkeras_factorize_alpha']
    return cfg


def convert_trace_model(gap_model, output_dir, trace=True):
    """Convert GAP model to a temporary trace project."""
    import hls4ml

    configure_rounding_saturation(gap_model)
    bit_exact = os.environ.get('BIT_EXACT', '0') == '1'
    hls_config = build_hls_config(gap_model, trace=trace, bit_exact=bit_exact)
    convert_kwargs = dict(
        hls_config=hls_config,
        output_dir=str(output_dir),
        backend='Vivado',
        io_type='io_stream',
        part='xczu4ev-sfvc784-1-i',
        clock_period=5,
    )
    if bit_exact:
        convert_kwargs['bit_exact'] = True
    hls_model = hls4ml.converters.convert_from_keras_model(gap_model, **convert_kwargs)
    hls_model.compile()
    return hls_model, hls_config
