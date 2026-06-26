#!/usr/bin/env python3
"""Top-1 accuracy: exported AXI csim GAP + PS Dense vs board benchmark."""
import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
TB = REPO / 'notebooks' / 'hls4ml_prj' / 'tb_data'
NPZ = REPO / 'deploy' / 'cifar10_bench.npz'
DENSE_NPZ = REPO / 'deploy' / 'dense_head.npz'
BOARD_JSON = REPO / 'results' / 'fpga_benchmark.json'
OUT_JSON = REPO / 'results' / 'gap_csim_ps_dense_accuracy.json'

sys.path.insert(0, str(REPO / 'scripts'))
from dma_infer_common import apply_ps_dense

CLASSES = [
    'airplane', 'automobile', 'bird', 'cat', 'deer',
    'dog', 'frog', 'horse', 'ship', 'truck',
]
GAP_DIM = int(os.environ.get('OUT_DIM', '24'))
N = int(os.environ.get('N_ACCURACY', '100'))


def load_csim_gaps(n):
    path = TB / 'csim_results.log'
    if not path.is_file():
        raise FileNotFoundError('missing %s — run csim with N_ACCURACY samples first' % path)
    lines = path.read_text(encoding='utf-8').strip().splitlines()
    if len(lines) < n:
        raise RuntimeError('csim has %d lines, need %d' % (len(lines), n))
    return [[float(x) for x in ln.split()] for ln in lines[:n]]


def top1_from_gaps(gaps, labels):
    preds = []
    for gap in gaps:
        scores = apply_ps_dense(gap[:GAP_DIM])
        preds.append(int(np.argmax(scores)))
    preds = np.asarray(preds, dtype=np.int32)
    labels = np.asarray(labels[: len(preds)], dtype=np.int32)
    acc = float(np.mean(preds == labels) * 100.0)
    return acc, preds.tolist()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--min-top1', type=float, default=None,
                    help='Minimum csim+PS Top-1 %% (e.g. 75)')
    args = ap.parse_args()

    if not NPZ.is_file():
        print('ERROR: missing %s' % NPZ, file=sys.stderr)
        return 1
    if DENSE_NPZ.is_file():
        os.environ.setdefault('DENSE_NPZ', str(DENSE_NPZ))

    data = np.load(NPZ, allow_pickle=True)
    labels = data['labels'].astype(np.int32)
    n = min(N, len(labels))

    gaps = load_csim_gaps(n)
    csim_acc, csim_preds = top1_from_gaps(gaps, labels)

    board_acc = None
    board_n = None
    if BOARD_JSON.is_file():
        board = json.loads(BOARD_JSON.read_text(encoding='utf-8'))
        board_acc = board.get('accuracy_top1')
        board_n = board.get('n_accuracy')

    overlap = min(n, board_n or 0)
    per_sample = []
    if overlap > 0 and BOARD_JSON.is_file():
        # Re-run board preds for overlap via stored benchmark if available
        pass

    report = {
        'n_samples': n,
        'gap_dim': GAP_DIM,
        'csim_ps_dense_top1_pct': round(csim_acc, 2),
        'board_top1_pct': board_acc,
        'board_n_samples': board_n,
        'delta_board_minus_csim_pct': (
            round(board_acc - csim_acc, 2) if board_acc is not None else None
        ),
        'verdict': None,
        'csim_source': str(TB / 'csim_results.log'),
    }

    if board_acc is not None:
        diff = abs(board_acc - csim_acc)
        if diff <= 3.0:
            report['verdict'] = (
                'PL and PS aligned: board ≈ csim+PS Dense (gap is model/quantization, not DMA/PS decode)'
            )
        elif board_acc < csim_acc - 3.0:
            report['verdict'] = (
                'PL likely worse than csim: board Top-1 below csim+PS Dense — check bit/firmware'
            )
        else:
            report['verdict'] = (
                'PS/board decode anomaly: board Top-1 above csim+PS Dense — check benchmark script'
            )

    passed = True
    if args.min_top1 is not None and csim_acc < args.min_top1:
        passed = False
        report['top1_gate_pass'] = False
    else:
        report['top1_gate_pass'] = True if args.min_top1 is not None else None
    if args.min_top1 is not None:
        report['min_top1_required'] = args.min_top1

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(report, indent=2), encoding='utf-8')

    print('=' * 60)
    print('  csim GAP + PS Dense Top-1  vs  board benchmark')
    print('=' * 60)
    print('  Samples      : %d' % n)
    print('  csim+PS Top-1: %.2f%%' % csim_acc)
    if board_acc is not None:
        print('  board Top-1  : %.2f%% (%s images)' % (board_acc, board_n))
        print('  delta (board - csim): %+.2f pp' % (board_acc - csim_acc))
    print('  verdict      : %s' % report['verdict'])
    print('written:', OUT_JSON)
    if args.min_top1 is not None and not passed:
        print(
            'TOP-1 GATE FAIL: csim+PS %.2f%% < required %.2f%%'
            % (csim_acc, args.min_top1),
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
