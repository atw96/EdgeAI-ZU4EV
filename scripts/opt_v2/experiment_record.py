#!/usr/bin/env python3
"""Write one timestamped results/opt_v2/<variant>_<utc>.json. Never overwrites."""
import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT_DIR = REPO / 'results' / 'opt_v2'


def _md5(path):
    path = Path(path)
    if not path.is_file():
        return None
    digest = hashlib.md5()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _load(path):
    path = Path(path)
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding='utf-8'))


def write_record(payload, variant):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    path = OUT_DIR / ('%s_%s.json' % (variant, stamp))
    suffix = 2
    while path.exists():
        path = OUT_DIR / ('%s_%s_%d.json' % (variant, stamp, suffix))
        suffix += 1
    path.write_text(json.dumps(payload, indent=2), encoding='utf-8')
    return path


def assemble(variant, notes, latency_json):
    sys.path.insert(0, str(REPO / 'scripts'))
    from v19_hls_config_common import RF_PER_LAYER
    from rf_planner import dense_variant, layers as planner_layers

    by_name = {row['name']: row for row in planner_layers()}
    rf_table = {}
    branches = []
    sum_p = 0
    per_layer = {}
    for name, layer in by_name.items():
        rf = int(RF_PER_LAYER[name])
        rf_table[name] = rf
        branches.append({'name': name, 'branch': dense_variant(layer['n_in'], rf)})
        sum_p += layer['n_in'] * layer['n_out'] // rf
        per_layer[name] = {'theory_px_x_rf': layer['px'] * rf}

    csynth = _load(REPO / 'results' / 'opt_v2' / 'csynth_layers.json')
    if csynth:
        for name, body in (csynth.get('reports') or {}).items():
            for layer in per_layer:
                if layer in name and body.get('latency'):
                    per_layer[layer]['csynth_latency_cycles'] = body['latency'].get('latency_max_cycles')

    gate = _load(REPO / 'results' / 'hls_csynth_gate.json') or {}
    latency = _load(latency_json) if latency_json else _load(REPO / 'results' / 'fpga_latency_compare.json')
    fpga = (latency or {}).get('fpga') or {}
    payload = {
        'variant': variant,
        'rf_table': rf_table,
        'sumP': sum_p,
        'dense_variant': branches,
        'csynth_per_layer_cycles': per_layer,
        'csynth_util': (gate.get('used') if gate else None),
        'impl_LUT': None,
        'impl_DSP': None,
        'impl_BRAM': None,
        'impl_URAM': None,
        'WNS': None,
        'bit_md5': _md5(REPO / 'deploy' / 'cifar10_accel.bit'),
        'hwh_md5': _md5(REPO / 'deploy' / 'cifar10_accel.hwh'),
        'latency': {
            'reset_each': fpga.get('reset_each_dma_ms'),
            'no_reset': fpga.get('no_reset_dma_ms'),
        },
        'ps_only_ms': (fpga.get('gap_readback_only_ms') or {}).get('median') if fpga else None,
        'top1_keras': None,
        'top1_csim': None,
        'top1_board': fpga.get('accuracy_top1_reset_each') if fpga else None,
        'mcnemar_p': None,
        'aa_holes': None,
        'notes': notes,
    }
    return payload


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--variant', required=True)
    ap.add_argument('--notes', default='')
    ap.add_argument('--latency-json', default='')
    ap.add_argument('--from-json', default='', help='Use this JSON object instead of assembling')
    args = ap.parse_args()
    if args.from_json:
        payload = json.loads(Path(args.from_json).read_text(encoding='utf-8'))
        payload.setdefault('variant', args.variant)
    else:
        payload = assemble(args.variant, args.notes, args.latency_json or None)
    path = write_record(payload, args.variant)
    print(path)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
