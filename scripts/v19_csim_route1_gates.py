#!/usr/bin/env python3
"""Route 1 csim gates: Top-1 primary (fail), MAE auxiliary (warn unless MAE_HARD_FAIL=1)."""
import argparse
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ALIGN_JSON = REPO / 'results' / 'gap_csim_keras_align.json'
TOP1_JSON = REPO / 'results' / 'gap_csim_ps_dense_accuracy.json'
OUT_JSON = REPO / 'results' / 'v19_route1_gates.json'


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--min-top1', type=float, default=float(os.environ.get('CSIM_TOP1_MIN', '75')))
    ap.add_argument('--max-mae', type=float, default=float(os.environ.get('CSIM_MAE_MAX', '0.35')))
    ap.add_argument('--align-report', default=str(ALIGN_JSON))
    ap.add_argument('--top1-report', default=str(TOP1_JSON))
    args = ap.parse_args()

    mae_hard = os.environ.get('MAE_HARD_FAIL', '0') == '1'
    top1_pass = False
    mae_pass = True
    top1_val = None
    mae_val = None
    errors = []

    top1_path = Path(args.top1_report)
    if not top1_path.is_file():
        errors.append('missing Top-1 report %s — run gap_csim_ps_dense_accuracy.py' % top1_path)
    else:
        top1_data = json.loads(top1_path.read_text(encoding='utf-8'))
        top1_val = float(top1_data['csim_ps_dense_top1_pct'])
        top1_pass = top1_val >= args.min_top1

    align_path = Path(args.align_report)
    if not align_path.is_file():
        errors.append('missing MAE report %s — run gap_csim_keras_align.py' % align_path)
    else:
        align_data = json.loads(align_path.read_text(encoding='utf-8'))
        mae_val = float(align_data['summary']['csim_vs_keras_mae_mean'])
        mae_pass = mae_val <= args.max_mae

    result = {
        'route': 'route1_top1_primary',
        'top1_pct': top1_val,
        'min_top1_required': args.min_top1,
        'top1_pass': top1_pass,
        'mae_mean': mae_val,
        'max_mae_allowed': args.max_mae,
        'mae_pass': mae_pass,
        'mae_hard_fail': mae_hard,
        'overall_pass': top1_pass and (mae_pass or not mae_hard),
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(result, indent=2), encoding='utf-8')

    print('=' * 60)
    print('  Route 1 gates (Top-1 primary, MAE auxiliary)')
    print('=' * 60)
    if top1_val is not None:
        status = 'PASS' if top1_pass else 'FAIL'
        print('  Top-1 (csim+PS Dense): %.2f%%  required >= %.2f%%  [%s]' % (
            top1_val, args.min_top1, status))
    if mae_val is not None:
        status = 'PASS' if mae_pass else ('FAIL' if mae_hard else 'WARN')
        print('  MAE (csim vs Keras):   %.4f   max %.4f  [%s]' % (
            mae_val, args.max_mae, status))
    print('written:', OUT_JSON)

    if errors:
        for e in errors:
            print('ERROR:', e, file=sys.stderr)
        return 2

    rc = 0
    if not top1_pass:
        print(
            'TOP-1 GATE FAIL: csim+PS %.2f%% < required %.2f%%'
            % (top1_val, args.min_top1),
            file=sys.stderr,
        )
        rc = 1
    if not mae_pass:
        msg = 'MAE GATE: %.4f > %.4f' % (mae_val, args.max_mae)
        if mae_hard:
            print('MAE GATE FAIL: ' + msg, file=sys.stderr)
            rc = 1
        else:
            print('MAE auxiliary WARN: ' + msg + ' (set MAE_HARD_FAIL=1 to fail)', file=sys.stderr)

    if rc == 0:
        print('ROUTE1 GATES PASS')
    return rc


if __name__ == '__main__':
    sys.exit(main())
