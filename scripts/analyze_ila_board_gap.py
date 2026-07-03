#!/usr/bin/env python3
"""Compare ILA output_stream TDATA beats vs board_fetch_gap DRAM vs csim."""
import argparse
import json
import os
import re
import struct
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'scripts'))
from dma_infer_common import apply_ps_dense
from slot32_layout import decode_serial32_raw

TB = REPO / 'notebooks' / 'hls4ml_prj' / 'tb_data'
SCALE = int(os.environ.get('OUT_FIXED_SCALE', '1024'))
OUT_DIM = int(os.environ.get('OUT_DIM', '24'))


def parse_ila_hex(text):
    vals = []
    for tok in re.split(r'[\s,]+', text.strip()):
        if not tok:
            continue
        tok = tok.strip().strip("'")
        if tok.startswith('h'):
            tok = tok[1:]
        vals.append(int(tok, 16) & 0xFFFFFFFF)
    return vals


def s16_word(word):
    v = word & 0xFFFF
    return v - 0x10000 if v >= 0x8000 else v


def gap_from_ila_words(words):
    return [s16_word(w) / float(SCALE) for w in words[:OUT_DIM]]


def gap_from_dram_serial(raw):
    return decode_serial32_raw(raw, SCALE, OUT_DIM)


def gap_from_dram_hole_pairs(raw):
    """Legacy axis_dw_s2mm path: 2 data words + 2 hole words in DRAM."""
    scores = []
    word = 0
    while len(scores) < OUT_DIM and (word * 4) < len(raw):
        scores.append(struct.unpack_from('<h', raw, word * 4)[0] / float(SCALE))
        word += 1
        if len(scores) % 2 == 0:
            word += 2
    return scores


def load_csim_beats(sample_idx=0):
    path = TB / 'csim_axis_beats.log'
    lines = path.read_text(encoding='utf-8').strip().splitlines()
    words = [int(x, 16) for x in lines[sample_idx].split()]
    return gap_from_ila_words(words)


def top1_from_gap(gap, label=None):
    dense = os.environ.get('DENSE_NPZ', str(REPO / 'deploy' / 'dense_head.npz'))
    os.environ['DENSE_NPZ'] = dense
    try:
        scores = apply_ps_dense(gap[:OUT_DIM])
    except FileNotFoundError:
        return {'error': 'dense_head.npz missing'}
    pred = int(np.argmax(scores))
    out = {'pred': pred, 'scores': [round(float(s), 4) for s in scores]}
    if label is not None:
        out['label'] = int(label)
        out['correct'] = pred == int(label)
    return out


def mae(a, b):
    n = min(len(a), len(b))
    if n == 0:
        return float('nan')
    return float(np.mean(np.abs(np.array(a[:n], dtype=np.float64) - np.array(b[:n], dtype=np.float64))))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ila', help='ILA TDATA hex list (h193 h4ac ... or comma-separated)')
    ap.add_argument('--ila-file', type=Path, help='file with ILA hex tokens')
    ap.add_argument('--board-json', type=Path, default=REPO / 'results' / 'board_ila_fetch.json')
    ap.add_argument('--sample', type=int, default=0)
    ap.add_argument('--out', type=Path, default=REPO / 'results' / 'ila_board_gap_analysis.json')
    args = ap.parse_args()

    if args.ila_file:
        ila_text = args.ila_file.read_text(encoding='utf-8')
    elif args.ila:
        ila_text = args.ila
    else:
        print('ERROR: pass --ila or --ila-file', file=sys.stderr)
        return 1

    ila_words = parse_ila_hex(ila_text)
    ila_gap = gap_from_ila_words(ila_words)

    board = {}
    if args.board_json.is_file():
        text = args.board_json.read_text(encoding='utf-8').strip()
        for line in reversed(text.splitlines()):
            line = line.strip()
            if line.startswith('{'):
                board = json.loads(line)
                break

    raw = bytes.fromhex(board.get('raw_hex', ''))
    dram_serial = gap_from_dram_serial(raw) if raw else []
    dram_hole = gap_from_dram_hole_pairs(raw) if raw else []
    csim_gap = load_csim_beats(args.sample)
    label = board.get('label')

    report = {
        'ila_beat_count': len(ila_words),
        'ila_gap_head': [round(x, 6) for x in ila_gap[:8]],
        'dram_serial_head': [round(x, 6) for x in dram_serial[:8]],
        'dram_hole_pair_head': [round(x, 6) for x in dram_hole[:8]],
        'csim_gap_head': [round(x, 6) for x in csim_gap[:8]],
        'mae': {
            'ila_vs_dram_serial': round(mae(ila_gap, dram_serial), 6),
            'ila_vs_csim': round(mae(ila_gap, csim_gap), 6),
            'dram_serial_vs_csim': round(mae(dram_serial, csim_gap), 6),
            'ila_vs_dram_hole_pairs': round(mae(ila_gap[: len(dram_hole)], dram_hole), 6),
        },
        'dram_nonzero_words': sum(
            1 for i in range(OUT_DIM) if i * 4 < len(raw) and struct.unpack_from('<I', raw, i * 4)[0] != 0
        ),
        'top1': {
            'ila': top1_from_gap(ila_gap, label),
            'dram_serial': top1_from_gap(dram_serial, label) if dram_serial else None,
            'csim': top1_from_gap(csim_gap, label),
        },
        'verdict': '',
        'fix': '',
    }

    if report['dram_nonzero_words'] <= OUT_DIM // 2 and report['ila_beat_count'] == OUT_DIM:
        report['verdict'] = (
            'ILA shows %d serial beats on HLS output_stream; DRAM has %d nonzero words '
            'with hole pattern — S2MM path likely still has axis_dw_s2mm (16→32) while ILA '
            'taps HLS before the converter.'
        ) % (report['ila_beat_count'], report['dram_nonzero_words'])
        report['fix'] = (
            'JTAG-program deploy/cifar10_accel.bit + .ltx from latest build '
            '(HLS_OUTPUT_AXIS_BITS=32, no axis_dw_s2mm). Then board_fetch DRAM should '
            'match ILA 1:1 with decode_serial32_raw.'
        )
    elif report['mae']['ila_vs_dram_serial'] < 0.02:
        report['verdict'] = 'ILA and DRAM serial decode match — PS decode path OK.'
        report['fix'] = 'None; run N=100 benchmark.'
    else:
        report['verdict'] = 'ILA and DRAM still differ — check same transfer / bit MD5 / csim stale.'
        report['fix'] = 'Re-arm ILA on board_fetch transfer; regenerate csim; verify bit MD5.'

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))
    print('written:', args.out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
