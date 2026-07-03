#!/usr/bin/env python3
"""Compare Keras GAP vs board DMA GAP for first N samples."""
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'scripts'))
from dma_infer_common import apply_ps_dense

BOARD_IP = os.environ.get('BOARD_IP', '192.168.1.40')
BOARD_PASS = os.environ.get('BOARD_PASS', 'root')
OUT_SCALE = int(os.environ.get('OUT_FIXED_SCALE', '1024'))
N = int(os.environ.get('N', '10'))


def keras_gap(payload):
    import tensorflow as tf
    from tensorflow import keras

    if not hasattr(keras_gap, '_model'):
        m = keras.models.load_model(
            str(REPO / 'notebooks' / 'model_int8_qkeras.h5'),
            compile=False,
        )
        keras_gap._model = keras.Model(m.input, m.get_layer('gap').output)
    x = np.frombuffer(payload, dtype=np.int16).astype(np.float32) / 1024.0
    x = x.reshape(1, 32, 32, 3)
    return keras_gap._model.predict(x, verbose=0)[0]


def fetch_board(idx):
    env = (
        'DENSE_NPZ=dense_head.npz OUT_DIM=24 OUT_BYTES=92 OUT_LAYOUT=gap_ps '
        'OUT_FIXED_SCALE=%d SAMPLE_IDX=%d'
    ) % (OUT_SCALE, idx)
    cmd = [
        'sshpass', '-p', BOARD_PASS,
        'ssh', '-o', 'StrictHostKeyChecking=no',
        'root@%s' % BOARD_IP,
        'cd /tmp/edgeai_bench && %s python3 -u board_fetch_gap.py' % env,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr[-400:])
    return json.loads(proc.stdout.strip().splitlines()[-1])


def main():
    os.environ['DENSE_NPZ'] = str(REPO / 'deploy' / 'dense_head.npz')
    data = np.load(REPO / 'deploy' / 'cifar10_bench.npz', allow_pickle=True)
    labels = data['labels'].astype(int)
    maes = []
    board_ok = 0
    for i in range(N):
        payload = bytes(data['payloads'][i])
        kg = keras_gap(payload)
        b = fetch_board(i)
        bg = np.array(b['gap_float'], dtype=np.float32)
        mae = float(np.mean(np.abs(kg - bg)))
        maes.append(mae)
        scores_k = apply_ps_dense(kg)
        scores_b = apply_ps_dense(bg)
        pk = int(np.argmax(scores_k))
        pb = int(np.argmax(scores_b))
        if pk == labels[i]:
            pass
        if pb == labels[i]:
            board_ok += 1
        print(
            'i=%d label=%d mae=%.4f keras_pred=%d board_pred=%d'
            % (i, labels[i], mae, pk, pb)
        )
    print('mean_mae=%.4f board_top1=%d/%d' % (np.mean(maes), board_ok, N))
    return 0


if __name__ == '__main__':
    sys.exit(main())
