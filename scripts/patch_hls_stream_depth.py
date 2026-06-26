#!/usr/bin/env python3
"""v11: shrink hls::stream FIFO depths in myproject.cpp to cut BRAM."""
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MYPROJECT = REPO / 'notebooks' / 'hls4ml_prj' / 'firmware' / 'myproject.cpp'

# (old_depth, new_depth)
DEPTH_MAP = [
    (1156, 128),
    (1024, 128),
    (324, 64),
    (256, 64),
    (100, 32),
    (64, 32),
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
    print('stream_depth changed=%s' % changed)
    return 0


if __name__ == '__main__':
    sys.exit(main())
