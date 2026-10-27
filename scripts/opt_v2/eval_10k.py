#!/usr/bin/env python3
"""Fixed-order CIFAR-10 evaluation and per-sample correct arrays.

Stages (run separately so a missing csim log does not block Keras):
  keras   full model Top-1
  gap_ps  GAP + deploy/dense_head.npz
  csim    notebooks/hls4ml_prj/tb_data/csim_results.log + PS dense
  board   correct array produced on the board (SAVE_PREDS from board_latency_compare)
  check   stop if any available pair differs by more than 1 point

Saves results/opt_v2/correct_<variant>_<stage>.npy with 1 = correct.
Does not overwrite an existing array; writes a timestamped sibling instead.
"""
import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'scripts'))
OUT_DIR = REPO / 'results' / 'opt_v2'


def _save(variant, stage, correct):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / ('correct_%s_%s.npy' % (variant, stage))
    if path.exists():
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        path = OUT_DIR / ('correct_%s_%s_%s.npy' % (variant, stage, stamp))
    np.save(path, np.asarray(correct, dtype=np.uint8))
    acc = 100.0 * float(np.mean(correct))
    print('%s top1=%.4f n=%d -> %s' % (stage, acc, len(correct), path))
    return path, acc


def _labels(n):
    os.environ.setdefault('PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION', 'python')
    from tensorflow import keras
    (_, _), (_, y_test) = keras.datasets.cifar10.load_data()
    y = y_test.reshape(-1).astype(np.int32)
    return y[:n]


def _images(n):
    from tensorflow import keras
    (_, _), (x_test, _) = keras.datasets.cifar10.load_data()
    x = x_test[:n].astype('float32') / 255.0
    return x


def stage_keras(variant, n, model_h5):
    os.environ.setdefault('PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION', 'python')
    from v19_hls_config_common import load_full_model
    model = load_full_model(model_h5)
    x = _images(n)
    y = _labels(n)
    pred = np.argmax(model.predict(x, verbose=0, batch_size=64), axis=1).astype(np.int32)
    return _save(variant, 'keras', (pred == y).astype(np.uint8))


def stage_gap_ps(variant, n, model_h5, dense_npz):
    os.environ.setdefault('PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION', 'python')
    import tensorflow as tf
    from dma_infer_common import apply_ps_dense
    from v19_hls_config_common import load_gap_model
    os.environ['DENSE_NPZ'] = str(dense_npz)
    gap_model = load_gap_model(model_h5)
    x = _images(n)
    y = _labels(n)
    gap = gap_model.predict(x, verbose=0, batch_size=64)
    pred = []
    for row in gap:
        scores = apply_ps_dense(row)
        pred.append(int(np.argmax(scores)))
    pred = np.asarray(pred, dtype=np.int32)
    del tf
    return _save(variant, 'gap_ps', (pred == y).astype(np.uint8))


def stage_csim(variant, n, csim_log, dense_npz, bench_npz):
    from dma_infer_common import apply_ps_dense
    os.environ['DENSE_NPZ'] = str(dense_npz)
    lines = Path(csim_log).read_text(encoding='utf-8').strip().splitlines()
    if bench_npz and Path(bench_npz).is_file():
        labels = np.load(bench_npz, allow_pickle=True)['labels'].astype(np.int32)
    else:
        labels = _labels(n)
    n = min(n, len(lines), len(labels))
    correct = []
    for i in range(n):
        gap = [float(x) for x in lines[i].split()]
        scores = apply_ps_dense(gap)
        correct.append(int(np.argmax(scores) == int(labels[i])))
    return _save(variant, 'csim', np.asarray(correct, dtype=np.uint8))


def stage_check(variant):
    arrays = {}
    for stage in ('keras', 'gap_ps', 'csim', 'board'):
        matches = sorted(OUT_DIR.glob('correct_%s_%s*.npy' % (variant, stage)))
        if matches:
            arrays[stage] = np.load(matches[-1])
    if len(arrays) < 2:
        print('check: fewer than 2 stages for %s (%s)' % (variant, list(arrays)))
        return 0
    names = list(arrays)
    failed = False
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a = arrays[names[i]]
            b = arrays[names[j]]
            n = min(len(a), len(b))
            ta = 100.0 * float(a[:n].mean())
            tb = 100.0 * float(b[:n].mean())
            print('%s %.4f vs %s %.4f (n=%d) delta=%.4f' % (names[i], ta, names[j], tb, n, abs(ta - tb)))
            if abs(ta - tb) > 1.0:
                failed = True
    if failed:
        print('ERROR: sources differ by >1 point; stop and check numerics', file=sys.stderr)
        return 1
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--stage', required=True, choices=('keras', 'gap_ps', 'csim', 'board', 'check'))
    ap.add_argument('--variant', required=True)
    ap.add_argument('--n', type=int, default=10000)
    ap.add_argument('--model-h5', default=str(REPO / 'notebooks' / 'model_int8_qkeras.h5'))
    ap.add_argument('--dense-npz', default=str(REPO / 'deploy' / 'dense_head.npz'))
    ap.add_argument('--csim-log', default=str(REPO / 'notebooks' / 'hls4ml_prj' / 'tb_data' / 'csim_results.log'))
    ap.add_argument('--bench-npz', default=str(REPO / 'deploy' / 'cifar10_bench_10k.npz'))
    ap.add_argument('--board-npy', default='', help='Existing correct array from the board')
    args = ap.parse_args()
    if args.stage == 'keras':
        stage_keras(args.variant, args.n, args.model_h5)
    elif args.stage == 'gap_ps':
        stage_gap_ps(args.variant, args.n, args.model_h5, args.dense_npz)
    elif args.stage == 'csim':
        stage_csim(args.variant, args.n, args.csim_log, args.dense_npz, args.bench_npz)
    elif args.stage == 'board':
        if not args.board_npy:
            print('ERROR: --board-npy is required (copy SAVE_PREDS output here)', file=sys.stderr)
            return 1
        correct = np.load(args.board_npy)
        _save(args.variant, 'board', correct[:args.n])
    else:
        return stage_check(args.variant)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
