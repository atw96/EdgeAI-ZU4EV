#!/usr/bin/env python3
"""Quick board vs csim raw beat compare for sample 0."""
import json
import subprocess
import struct
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'scripts'))
from slot32_layout import slot_beat_maps

TB = REPO / 'notebooks' / 'hls4ml_prj' / 'tb_data'
beats = [int(x, 16) for x in TB.joinpath('csim_axis_beats.log').read_text().splitlines()[0].split()]
cmd = [
    'sshpass', '-p', 'root',
    'ssh', '-o', 'StrictHostKeyChecking=no', 'root@192.168.1.40',
    'cd /tmp/edgeai_bench && OUT_DIM=24 OUT_BYTES=92 OUT_LAYOUT=gap_ps OUT_FIXED_SCALE=1024 SAMPLE_IDX=0 python3 -u board_fetch_gap.py',
]
proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
board = json.loads(proc.stdout.strip().splitlines()[-1])
raw = bytes.fromhex(board['raw_hex'])
board_words = [struct.unpack_from('<I', raw, w * 4)[0] for w in range(23)]
beat_lo, beat_hi, n_beats = slot_beat_maps(24)
matches = sum(1 for b in range(n_beats) if beat_lo[b] >= 0 and board_words[b] == beats[b])
writable = sum(1 for b in range(n_beats) if beat_lo[b] >= 0)
print('csim beat0', hex(beats[0]), 'board beat0', hex(board_words[0]))
print('writable match', matches, '/', writable)
print('board gap head', board['gap_float'][:4])
print('csim gap head', TB.joinpath('csim_results.log').read_text().splitlines()[0].split()[:4])
