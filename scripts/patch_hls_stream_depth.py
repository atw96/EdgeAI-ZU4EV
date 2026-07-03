#!/usr/bin/env python3
"""v11: tune hls::stream FIFO depths — BRAM vs LUT trade-off."""
import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MYPROJECT = REPO / 'notebooks' / 'hls4ml_prj' / 'firmware' / 'myproject.cpp'

# Profile: aggressive (SRL, save BRAM) | balanced (deeper FIFO → BRAM, save LUT)
_PROFILE = os.environ.get('HLS_STREAM_DEPTH_PROFILE', 'aggressive').lower()
if _PROFILE == 'balanced':
  # After narrow precision, BRAM headroom exists — deeper FIFOs cut SRL LUT.
  DEPTH_MAP = [
      (1156, 128),
      (1024, 128),
      (324, 64),
      (256, 64),
      (128, 64),
      (100, 32),
      (64, 32),
      (32, 64),
      (16, 64),
      (8, 32),
  ]
elif _PROFILE == 'moderate':
  # Trade some BRAM for LUT: push 16-bit streams to BRAM, keep relu shallow.
  DEPTH_MAP = [
      (1156, 64),
      (1024, 64),
      (324, 32),
      (256, 32),
      (128, 32),
      (100, 16),
      (64, 16),
      (32, 32),
      (16, 32),
      (8, 16),
  ]
elif _PROFILE == 'board_safe':
  # Board functional fix: min depth 32 (avoid aggressive 8/16 stall), cap 64 for BRAM<256.
  DEPTH_MAP = [
      (1156, 64),
      (1024, 64),
      (324, 32),
      (256, 32),
      (128, 32),
      (100, 32),
      (64, 32),
      (32, 32),
      (16, 32),
      (8, 32),
  ]
else:
  # aggressive: shallow FIFOs map to SRL/LUTRAM not BRAM
  DEPTH_MAP = [
      (1156, 32),
      (1024, 32),
      (324, 16),
      (256, 16),
      (128, 16),
      (100, 8),
      (64, 8),
  ]

PRAGMA_RE = re.compile(
    r'(#pragma HLS STREAM variable=\w+ depth=)(\d+)'
)


def main() -> int:
    if not MYPROJECT.is_file():
        print('ERROR: missing %s' % MYPROJECT, file=sys.stderr)
        return 1
    text = MYPROJECT.read_text(encoding='utf-8')
    lookup = {old: new for old, new in DEPTH_MAP}
    stats = {old: 0 for old, _ in DEPTH_MAP}
    changed = False

    def _replace(m):
        nonlocal changed
        prefix, depth_s = m.group(1), m.group(2)
        depth = int(depth_s)
        if depth not in lookup:
            return m.group(0)
        new_depth = lookup[depth]
        if new_depth == depth:
            return m.group(0)
        stats[depth] += 1
        changed = True
        return '%s%d' % (prefix, new_depth)

    new_text = PRAGMA_RE.sub(_replace, text)
    if changed:
        MYPROJECT.write_text(new_text, encoding='utf-8')
    for old, new in DEPTH_MAP:
        if stats[old]:
            print('stream depth %d -> %d: %d stream(s)' % (old, new, stats[old]))
    print('stream_depth profile=%s changed=%s' % (_PROFILE, changed))
    return 0


if __name__ == '__main__':
    sys.exit(main())
