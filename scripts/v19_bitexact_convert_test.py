#!/usr/bin/env python3
"""Quick test: bit_exact=True with/without pop Precision."""
import os
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TMP = REPO / 'notebooks' / 'hls4ml_prj_bitexact_test'

sys.path.insert(0, str(REPO / 'scripts'))
from v19_bitexact_probe import _firmware_layer_ops, _judge, _walk_graph  # noqa: E402
from v19_hls_config_common import build_hls_config, configure_rounding_saturation, load_gap_model  # noqa: E402


def run(pop_precision: bool, bit_exact: bool = False, skip_alpha: bool = False) -> None:
    import hls4ml

    os.environ.setdefault('GAP_ONLY', '1')
    gap = load_gap_model()
    configure_rounding_saturation(gap)
    cfg = build_hls_config(gap)
    if pop_precision:
        cfg['Model'].pop('Precision', None)
        for lcfg in cfg.get('LayerName', {}).values():
            lcfg.pop('Precision', None)
    if skip_alpha:
        cfg['SkipOptimizers'] = ['qkeras_factorize_alpha']

    if TMP.exists():
        shutil.rmtree(TMP, ignore_errors=True)

    kwargs = dict(
        hls_config=cfg,
        output_dir=str(TMP),
        backend='Vivado',
        io_type='io_stream',
        part='xczu4ev-sfvc784-1-i',
        clock_period=5,
    )
    if bit_exact:
        kwargs['bit_exact'] = True

    hls_model = hls4ml.converters.convert_from_keras_model(gap, **kwargs)
    try:
        hls_model.compile()
        compile_ok = True
    except Exception as exc:
        compile_ok = False
        print('compile FAIL:', exc)

    rows, fpq = _walk_graph(hls_model)
    fw = _firmware_layer_ops(TMP)
    judge = _judge(rows, fpq, fw, [l.name for l in gap.layers])
    print('pop_precision=', pop_precision, 'bit_exact=', bit_exact, 'skip_alpha=', skip_alpha, 'compile_ok=', compile_ok)
    print('judgment:', judge)
    for r in rows:
        if 'relu' in r.get('name', '') or 'input_qact' in r.get('name', ''):
            print(' ', r.get('name'), r.get('result_precision'))


if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'all'
    tests = {
        'legacy': (True, False, False),
        'bitexact': (True, True, False),
        'bitexact_skip_alpha': (True, True, True),
        'keep_bitexact_skip': (False, True, True),
    }
    if mode == 'all':
        for name, args in tests.items():
            print('===', name, '===')
            run(*args)
    elif mode in tests:
        print('===', mode, '===')
        run(*tests[mode])
