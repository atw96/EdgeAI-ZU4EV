#!/usr/bin/env python3
"""Probe standard QKeras convert — per-layer result_t (granularity=name)."""
import json
import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT_JSON = REPO / 'results' / 'v19_bitexact_probe.json'
OUT_MD = REPO / 'results' / 'v19_bitexact_probe.md'
TMP = REPO / 'notebooks' / 'hls4ml_prj_v19_bitexact_probe_tmp'

sys.path.insert(0, str(REPO / 'scripts'))
from v19_hls_config_common import (  # noqa: E402
    build_hls_config,
    configure_rounding_saturation,
    load_gap_model,
)


def _precision_str(node):
    try:
        out = node.get_output_variable()
        if out is None:
            return None
        prec = getattr(out, 'type', None)
        if prec is None:
            return None
        p = getattr(prec, 'precision', prec)
        return str(p)
    except Exception:
        return None


def _walk_graph(hls_model):
    rows = []
    fpq_count = 0
    graph = getattr(hls_model, 'graph', None)
    if graph is None:
        return rows, fpq_count

    nodes = []
    if hasattr(graph, 'nodes'):
        nodes = list(graph.nodes.values()) if isinstance(graph.nodes, dict) else list(graph.nodes)
    elif hasattr(hls_model, 'get_layers'):
        nodes = hls_model.get_layers()

    for node in nodes:
        cname = type(node).__name__
        name = getattr(node, 'name', cname)
        if 'FixedPointQuantizer' in cname or 'Quantizer' in cname:
            fpq_count += 1
        rows.append({
            'name': name,
            'class_name': cname,
            'result_precision': _precision_str(node),
            'activation': getattr(node, 'attributes', {}).get('activation') if hasattr(node, 'attributes') else None,
        })
    return rows, fpq_count


def _parse_defines(defines_path):
    if not defines_path.is_file():
        return {}
    text = defines_path.read_text(encoding='utf-8')
    out = {}
    for line in text.splitlines():
        m = re.match(r'typedef\s+nnet::array<ap_fixed<(\d+),(\d+)[^>]*>,\s*(\d+)\*1>\s+(\w+);', line)
        if m:
            out[m.group(4)] = {'w': int(m.group(1)), 'i': int(m.group(2)), 'ap_fixed': 'ap_fixed<%s,%s>' % (m.group(1), m.group(2))}
        m2 = re.match(r'typedef\s+ap_fixed<(\d+),(\d+)[^>]*>\s+(\w+);', line)
        if m2:
            out[m2.group(3)] = {'w': int(m2.group(1)), 'i': int(m2.group(2)), 'ap_fixed': 'ap_fixed<%s,%s>' % (m2.group(1), m2.group(2))}
    return out


def _firmware_layer_ops(prj_dir):
    cpp = prj_dir / 'firmware' / 'myproject.cpp'
    if not cpp.is_file():
        return []
    rows = []
    for line in cpp.read_text(encoding='utf-8').splitlines():
        m = re.search(r'nnet::(\w+)<[^>]+>\([^)]+\);\s*//\s*(\S+)', line)
        if m:
            rows.append({'op': m.group(1), 'layer': m.group(2)})
    return rows


def _is_narrow_relu_precision(prec_str):
    if not prec_str:
        return False
    s = str(prec_str)
    if '16,6' in s:
        return False
    if 'ufixed<6,2' in s or 'fixed<6,2' in s:
        return True
    if 'ufixed<6,3' in s:
        return True
    return False


def _judge(rows, fpq_count, fw_ops, keras_layers):
    relu_rows = [r for r in rows if r.get('name', '').startswith('relu_conv')]
    relu3b = next((r for r in relu_rows if r.get('name') == 'relu_conv3b'), None)
    relu_wide = [r for r in relu_rows if r.get('result_precision') and '16,6' in str(r.get('result_precision'))]
    relu_narrow = [r for r in relu_rows if _is_narrow_relu_precision(r.get('result_precision'))]

    if len(relu_narrow) == len(relu_rows) and relu_rows:
        verdict = 'qkeras_precision_narrow'
        branch = 'convert_align_gates'
    elif relu_wide:
        verdict = 'precision_still_wide_16_6'
        branch = 'fix_config_granularity_name'
    else:
        verdict = 'mixed_or_unknown'
        branch = 'investigate_layer_precision'

    return {
        'verdict': verdict,
        'recommended_branch': branch,
        'fixed_point_quantizer_count': fpq_count,
        'relu_node_count': len(relu_rows),
        'relu_narrow_count': len(relu_narrow),
        'relu_wide_16_6_count': len(relu_wide),
        'relu_conv3b_precision': relu3b.get('result_precision') if relu3b else None,
        'firmware_relu_ops': [o for o in fw_ops if 'relu' in o.get('layer', '')],
    }


def main() -> int:
    import hls4ml
    import shutil

    os.environ.setdefault('GAP_ONLY', '1')
    gap = load_gap_model()
    keras_names = [l.name for l in gap.layers]
    print('GAP keras layers:', keras_names[:8], '... total', len(keras_names))

    configure_rounding_saturation(gap)
    bit_exact = os.environ.get('BIT_EXACT', '0') == '1'
    hls_config = build_hls_config(gap, trace=False, bit_exact=bit_exact)
    print('hls4ml', hls4ml.__version__)
    print('bit_exact probe:', bit_exact)
    relu_prec = hls_config.get('LayerName', {}).get('relu_conv3b', {}).get('Precision', {})
    print('relu_conv3b config Precision:', relu_prec)

    if TMP.exists():
        shutil.rmtree(TMP, ignore_errors=True)

    convert_kwargs = dict(
        hls_config=hls_config,
        output_dir=str(TMP),
        backend='Vivado',
        io_type='io_stream',
        part='xczu4ev-sfvc784-1-i',
        clock_period=5,
    )
    if bit_exact:
        convert_kwargs['bit_exact'] = True
    hls_model = hls4ml.converters.convert_from_keras_model(gap, **convert_kwargs)
    hls_model.compile()

    rows, fpq_count = _walk_graph(hls_model)
    defines = _parse_defines(TMP / 'firmware' / 'defines.h')
    fw_ops = _firmware_layer_ops(TMP)
    judge = _judge(rows, fpq_count, fw_ops, keras_names)

    report = {
        'route': 'bitexact_probe' if bit_exact else 'qkeras_name_granularity_probe',
        'bit_exact': bit_exact,
        'hls4ml_version': hls4ml.__version__,
        'keras_layer_names': keras_names,
        'graph_nodes': rows,
        'defines_typedefs_count': len(defines),
        'defines_sample': {k: defines[k] for k in list(defines)[:12]},
        'firmware_ops': fw_ops,
        'judgment': judge,
    }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(report, indent=2), encoding='utf-8')

    md = ['# v19 QKeras name-granularity probe', '',
          '## Judgment', '',
          '- verdict: **%s**' % judge['verdict'],
          '- branch: **%s**' % judge['recommended_branch'],
          '- relu narrow (ufixed<6,2>): %d / %d' % (judge['relu_narrow_count'], judge['relu_node_count']),
          '- relu wide 16,6: %d / %d' % (judge['relu_wide_16_6_count'], judge['relu_node_count']),
          '- relu_conv3b: %s' % judge.get('relu_conv3b_precision'),
          '', '## Firmware ops (sample)', '',
          '| op | layer |', '|---|---|']
    for o in fw_ops[:30]:
        md.append('| %s | %s |' % (o['op'], o['layer']))
    md.append('')
    md.append('## Graph nodes (activation/relu)')
    md.append('| name | class | result_precision |')
    md.append('|---|---|---|')
    for r in rows:
        if any(k in r.get('name', '') for k in ('relu', 'qact', 'input_qact', 'Activation')):
            md.append('| %s | %s | %s |' % (r.get('name'), r.get('class_name'), r.get('result_precision')))
    OUT_MD.write_text('\n'.join(md) + '\n', encoding='utf-8')

    print(json.dumps(judge, indent=2))
    print('written:', OUT_JSON)
    print('written:', OUT_MD)
    return 0


if __name__ == '__main__':
    sys.exit(main())
