#!/usr/bin/env python3
import json
import os
import struct
import subprocess
import sys
from pathlib import Path

import numpy as np

REPO = Path('/home/atw/Edge_AI_Acc/claude/EdgeAI-ZU4EV_Claude')
sys.path.insert(0, str(REPO / 'scripts'))
from slot32_layout import decode_serial32_raw, decode_slot32_raw

OUT_JSON = REPO / 'results' / 'gap_axi_csim_board_align.json'
BOARD_IP = os.environ.get('BOARD_IP', '192.168.1.40')
BOARD_PASS = os.environ.get('BOARD_PASS', 'root')
OUT_SCALE = 1024
OUT_DIM = 24
OUT_BYTES = 96

def mae(a, b):
    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    return float(np.mean(np.abs(a - b)))

def fetch_board(mode, idx=0):
    env = (
        'OUT_DIM=%d OUT_BYTES=%d OUT_LAYOUT=gap_ps OUT_FIXED_SCALE=%d OUTPUT_PACK_MODE=%s SAMPLE_IDX=%d'
    ) % (OUT_DIM, OUT_BYTES, OUT_SCALE, mode, idx)
    cmd = [
        'sshpass', '-p', BOARD_PASS,
        'ssh', '-o', 'StrictHostKeyChecking=no',
        'root@%s' % BOARD_IP,
        'cd /tmp/edgeai_bench && %s python3 -u board_fetch_gap.py' % env,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
    if proc.returncode != 0:
        print('SSH/board_fetch failed mode=%s' % mode, file=sys.stderr)
        print(proc.stderr[-800:], file=sys.stderr)
        print(proc.stdout[-400:], file=sys.stderr)
        raise SystemExit(1)
    return json.loads(proc.stdout.strip().splitlines()[-1])

report = json.loads(OUT_JSON.read_text(encoding='utf-8'))
s0 = report['samples'][0]
raw_hex = s0['board_raw_hex']
csim_gap = s0['csim_gap']
raw = bytes.fromhex(raw_hex)

print('=== JSON sample 0 ===')
print('board_raw_hex len(bytes):', len(raw))
print('csim_gap[:6]:', csim_gap[:6])

dec_serial = decode_serial32_raw(raw, OUT_SCALE, OUT_DIM)
dec_slot = decode_slot32_raw(raw, OUT_SCALE, OUT_DIM)
dec_slot92 = decode_slot32_raw(raw[:92], OUT_SCALE, OUT_DIM)

mae_serial = mae(dec_serial, csim_gap)
mae_slot = mae(dec_slot, csim_gap)
mae_slot92 = mae(dec_slot92, csim_gap)

print('\n=== MAE vs csim_gap (from align JSON raw) ===')
print('decode_serial32_raw scale=1024 n=24:', mae_serial)
print('decode_slot32_raw   scale=1024 n=24:', mae_slot)
print('decode_slot32_raw   first 92 bytes only:', mae_slot92)

print('\n=== Fresh board_fetch_gap sample 0 ===')
board_slot = fetch_board('slot', 0)
board_serial = fetch_board('serial', 0)
for mode, b in [('slot', board_slot), ('serial', board_serial)]:
    gf = b['gap_float']
    print('OUTPUT_PACK_MODE=%s gap_float MAE vs csim: %.6f' % (mode, mae(gf, csim_gap)))
    print('  gap_float[:6]:', gf[:6])

raw_fresh = bytes.fromhex(board_slot['raw_hex'])
board_words = [struct.unpack_from('<I', raw_fresh, w * 4)[0] for w in range(OUT_BYTES // 4)]
print('\n=== board_words[0:12] (fresh fetch, slot mode) ===')
for i in range(12):
    w = board_words[i]
    print('  [%2d] 0x%08x  %d' % (i, w, w))

print('\nFresh slot vs serial gap_float MAE:', mae(board_slot['gap_float'], board_serial['gap_float']))
print('raw_hex identical slot vs serial:', board_slot['raw_hex'] == board_serial['raw_hex'])

candidates = [
    ('decode_serial32_raw (JSON raw)', mae_serial),
    ('decode_slot32_raw full (JSON raw)', mae_slot),
    ('decode_slot32_raw 92B (JSON raw)', mae_slot92),
    ('board_fetch OUTPUT_PACK_MODE=slot', mae(board_slot['gap_float'], csim_gap)),
    ('board_fetch OUTPUT_PACK_MODE=serial', mae(board_serial['gap_float'], csim_gap)),
]
print('\n=== RANKING (lower MAE = better) ===')
for name, m in sorted(candidates, key=lambda x: x[1]):
    print('  %-40s %.6f' % (name, m))
best_name, best_mae = min(candidates, key=lambda x: x[1])
if 'serial' in best_name and 'slot' not in best_name.replace('serial', ''):
    layout = 'serial'
elif 'slot' in best_name:
    layout = 'slot'
else:
    layout = 'serial' if mae_serial < mae_slot else 'slot'
print('\nBest match:', best_name, 'MAE=%.6f' % best_mae)
print('Inferred hardware DMA layout:', layout)
