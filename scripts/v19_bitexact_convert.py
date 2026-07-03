#!/usr/bin/env python3
"""GAP-only hls4ml 1.x convert: standard QKeras granularity=name, model must include input_qact."""
import json
import os
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
HLS_OUT = REPO / 'notebooks' / 'hls4ml_prj'
MODEL_H5 = REPO / 'notebooks' / 'model_int8_qkeras.h5'

sys.path.insert(0, str(REPO / 'scripts'))
from v19_bitexact_probe import _firmware_layer_ops, _judge, _walk_graph  # noqa: E402
from v19_hls_config_common import (  # noqa: E402
    build_hls_config,
    configure_rounding_saturation,
    load_gap_model,
)


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
    gap = load_gap_model()
    configure_rounding_saturation(gap)
    print('GAP model layers (head):', [l.name for l in gap.layers[:6]])
    bit_exact = os.environ.get('BIT_EXACT', '0') == '1'
    hls_config = build_hls_config(gap, bit_exact=bit_exact)

    print('hls4ml', hls4ml.__version__)
    print('granularity: name')
    print('bit_exact:', bit_exact)
    print('relu_conv3b Precision:', hls_config.get('LayerName', {}).get('relu_conv3b', {}).get('Precision'))

    backup_hls_out()

    convert_kwargs = dict(
        hls_config=hls_config,
        output_dir=str(HLS_OUT),
        backend='Vivado',
        io_type='io_stream',
        part='xczu4ev-sfvc784-1-i',
        clock_period=5,
    )
    if bit_exact:
        convert_kwargs['bit_exact'] = True
    hls_model = hls4ml.converters.convert_from_keras_model(gap, **convert_kwargs)
    hls_model.compile()
    hls_model.write()

    rows, fpq_count = _walk_graph(hls_model)
    fw_ops = _firmware_layer_ops(HLS_OUT)
    judge = _judge(rows, fpq_count, fw_ops, [l.name for l in gap.layers])
    print('fixed_point_quantizer_count:', fpq_count)
    print('bit_exact_active:', fpq_count > 0)

    defines = HLS_OUT / 'firmware' / 'defines.h'
    if defines.exists():
        for line in defines.read_text(encoding='utf-8').splitlines():
            if 'result_t' in line or ('input' in line and 'typedef' in line):
                print('defines:', line.strip())

    summary = {
        'route': 'qkeras_name_granularity_route1' if not bit_exact else 'bitexact_alpha1_route1',
        'hls4ml_version': hls4ml.__version__,
        'granularity': 'name',
        'bit_exact': bit_exact,
        'fixed_point_quantizer_count': fpq_count,
        'bit_exact_active': fpq_count > 0,
        'judgment': judge,
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
