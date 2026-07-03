#!/usr/bin/env python3
"""
Compare exported myproject_axi HLS csim (GAP 24) vs board DMA raw beats.
Uses csim_results.log + csim_axis_beats.log from Vivado csim.
"""
import json
import os
import struct
import subprocess
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
HLS_DIR = REPO / 'notebooks' / 'hls4ml_prj'
TB = HLS_DIR / 'tb_data'
OUT_JSON = REPO / 'results' / 'gap_axi_csim_board_align.json'
NPZ = REPO / 'deploy' / 'cifar10_bench.npz'

BOARD_IP = os.environ.get('BOARD_IP', '192.168.1.40')
BOARD_PASS = os.environ.get('BOARD_PASS', 'root')
OUT_SCALE = int(os.environ.get('OUT_FIXED_SCALE', '1024'))
OUT_DIM = int(os.environ.get('OUT_DIM', '24'))
OUT_BYTES = int(os.environ.get('OUT_BYTES', '96'))
OUTPUT_PACK_MODE = os.environ.get('OUTPUT_PACK_MODE', 'slot').lower()

sys.path.insert(0, str(REPO / 'scripts'))
from slot32_layout import slot32_word_map, slot_beat_maps


def load_csim(n):
    gap_lines = (TB / 'csim_results.log').read_text(encoding='utf-8').strip().splitlines()
    beat_lines = (TB / 'csim_axis_beats.log').read_text(encoding='utf-8').strip().splitlines()
    if len(gap_lines) < n or len(beat_lines) < n:
        raise RuntimeError('csim logs have %d/%d lines, need %d' % (
            len(gap_lines), len(beat_lines), n))
    gaps = []
    beats = []
    for i in range(n):
        gaps.append([float(x) for x in gap_lines[i].split()])
        beats.append([int(x, 16) for x in beat_lines[i].split()])
    return gaps, beats


def fetch_board(idx):
    env = (
        'OUT_DIM=%d OUT_BYTES=%d OUT_LAYOUT=gap_ps OUT_FIXED_SCALE=%d OUTPUT_PACK_MODE=%s SAMPLE_IDX=%d'
    ) % (OUT_DIM, OUT_BYTES, OUT_SCALE, OUTPUT_PACK_MODE, idx)
    cmd = [
        'sshpass', '-p', BOARD_PASS,
        'ssh', '-o', 'StrictHostKeyChecking=no',
        'root@%s' % BOARD_IP,
        'cd /tmp/edgeai_bench && %s python3 -u board_fetch_gap.py' % env,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr[-400:])
    return json.loads(proc.stdout.strip().splitlines()[-1])


def board_words_from_raw(raw_hex):
    raw = bytes.fromhex(raw_hex)
    return [struct.unpack_from('<I', raw, w * 4)[0] for w in range(OUT_BYTES // 4)]


def csim_words_from_beats(beat_hex_list):
    """Map beat index -> 32-bit word at DRAM word index (same as beat index for stream)."""
    beat_lo, beat_hi, n_beats = slot_beat_maps(OUT_DIM)
    words = {}
    for beat, word in enumerate(beat_hex_list):
        words[beat] = word
    return words, n_beats


def main():
    n = int(os.environ.get('N_GAP_COMPARE', '10'))
    if not (TB / 'csim_results.log').is_file():
        print('ERROR: run run_gap_axi_csim.sh first', file=sys.stderr)
        return 1
    csim_gaps, csim_beats = load_csim(n)

    pack_serial = OUTPUT_PACK_MODE == 'serial'
    if pack_serial:
        n_beats = OUT_DIM
        beat_lo = list(range(OUT_DIM))
        beat_hi = [-1] * OUT_DIM
    else:
        beat_lo, beat_hi, n_beats = slot_beat_maps(OUT_DIM)
    samples = []
    gap_mae = []
    beat_match_pct = []
    word_match_pct = []

    for i in range(n):
        board = fetch_board(i)
        raw = board['raw_hex']
        board_words = board_words_from_raw(raw)
        if pack_serial:
            beat_cmp = []
            slot_cmp = []
            csim_beat_list = csim_beats[i]
            for beat in range(n_beats):
                bw = board_words[beat] if beat < len(board_words) else 0
                cw = csim_beat_list[beat] if beat < len(csim_beat_list) else 0
                beat_cmp.append({
                    'beat': beat,
                    'writable': True,
                    'board_word': bw,
                    'csim_word': cw,
                    'match': bw == cw,
                    'lo_idx': beat,
                    'hi_idx': -1,
                })
        else:
            csim_words, _ = csim_words_from_beats(csim_beats[i])
            beat_cmp = []
            for beat in range(n_beats):
                bw = board_words[beat] if beat < len(board_words) else 0
                cw = csim_words.get(beat, 0)
                is_writable = beat_lo[beat] >= 0
                beat_cmp.append({
                    'beat': beat,
                    'writable': is_writable,
                    'board_word': bw,
                    'csim_word': cw,
                    'match': (bw == cw) if is_writable else None,
                    'lo_idx': beat_lo[beat],
                    'hi_idx': beat_hi[beat],
                })

            slot_cmp = []
            for word_idx, logits in slot32_word_map(OUT_DIM).items():
                bw = board_words[word_idx] if word_idx < len(board_words) else 0
                cw = csim_words.get(word_idx, 0)
                slot_cmp.append({
                    'word_idx': word_idx,
                    'logits': list(logits),
                    'board_word': bw,
                    'csim_word': cw,
                    'match': bw == cw,
                })

        bg = np.array(board['gap_float'], dtype=np.float64)
        cg = np.array(csim_gaps[i], dtype=np.float64)
        mae = float(np.mean(np.abs(bg - cg)))
        gap_mae.append(mae)
        bm = float(np.mean([r['match'] for r in beat_cmp if r.get('writable')]) * 100)
        wm = float(np.mean([r['match'] for r in (slot_cmp if slot_cmp else beat_cmp)]) * 100)
        beat_match_pct.append(bm)
        word_match_pct.append(wm)

        samples.append({
            'sample': i,
            'label': int(board['label']),
            'gap_mae_board_vs_csim': mae,
            'beat_match_pct': bm,
            'writable_word_match_pct': wm,
            'csim_gap': [round(v, 6) for v in csim_gaps[i]],
            'board_gap': board['gap_float'],
            'beat_compare': beat_cmp,
            'writable_word_compare': slot_cmp,
            'board_raw_hex': raw,
        })

    report = {
        'n_samples': n,
        'out_scale': OUT_SCALE,
        'out_bytes': OUT_BYTES,
        'n_beats': n_beats,
        'summary': {
            'gap_mae_mean': float(np.mean(gap_mae)),
            'gap_mae_max': float(np.max(gap_mae)),
            'beat_word_match_mean_pct': float(np.mean(beat_match_pct)),
            'writable_slot_match_mean_pct': float(np.mean(word_match_pct)),
        },
        'verdict': '',
        'samples': samples,
    }
    match_key = report['summary']['beat_word_match_mean_pct'] if pack_serial else report['summary']['writable_slot_match_mean_pct']
    if match_key > 80:
        report['verdict'] = 'board DRAM words match exported AXI csim — decode OK, check float scale if gap_mae high'
    elif report['summary']['beat_word_match_mean_pct'] > 50:
        report['verdict'] = 'partial beat match — DMA slot or bit timing issue'
    else:
        report['verdict'] = 'board raw != exported csim — PL/bit stale or wrong IP loaded'

    OUT_JSON.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report['summary'], indent=2))
    print('verdict:', report['verdict'])
    print('written:', OUT_JSON)
    return 0


if __name__ == '__main__':
    sys.exit(main())
