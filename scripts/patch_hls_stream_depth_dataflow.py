#!/usr/bin/env python3
"""Restore inter-layer stream depths for DATAFLOW (reverse v14 shrink)."""
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MYPROJECT = REPO / 'notebooks' / 'hls4ml_prj' / 'firmware' / 'myproject.cpp'

# v14 shrunk these; restore hls4ml defaults for pipelined layers.
DEPTH_MAP = [
    (4, 32),
    (8, 64),
]

PRAGMA_RE = re.compile(r'(#pragma HLS STREAM variable=\w+ depth=)(\d+)')


def main() -> int:
    if not MYPROJECT.is_file():
        print('ERROR: missing %s' % MYPROJECT, file=sys.stderr)
        return 1
    text = MYPROJECT.read_text(encoding='utf-8')
    lookup = {old: new for old, new in DEPTH_MAP}
    stats = {}
    changed = False

    def _replace(m):
        nonlocal changed
        depth = int(m.group(2))
        if depth not in lookup:
            return m.group(0)
        new_depth = lookup[depth]
        stats[depth] = stats.get(depth, 0) + 1
        changed = True
        return '%s%d' % (m.group(1), new_depth)

    new_text = PRAGMA_RE.sub(_replace, text)
    if changed:
        MYPROJECT.write_text(new_text, encoding='utf-8')
    for old, new in DEPTH_MAP:
        if stats.get(old):
            print('depth %d -> %d: %d stream(s)' % (old, new, stats[old]))
    print('stream_depth_dataflow changed=%s' % changed)
    return 0


if __name__ == '__main__':
    sys.exit(main())
