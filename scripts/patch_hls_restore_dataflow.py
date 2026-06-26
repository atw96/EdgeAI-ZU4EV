#!/usr/bin/env python3
"""Restore top-level DATAFLOW in myproject.cpp (required for stream layer deadlock)."""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MYPROJECT = REPO / 'notebooks' / 'hls4ml_prj' / 'firmware' / 'myproject.cpp'
PRAGMA = '    #pragma HLS DATAFLOW '
COMMENT = '    // v14: DATAFLOW removed for resource fit (sequential layers)'


def main() -> int:
    if not MYPROJECT.is_file():
        print('ERROR: missing %s' % MYPROJECT, file=sys.stderr)
        return 1
    text = MYPROJECT.read_text(encoding='utf-8')
    if '#pragma HLS DATAFLOW' in text:
        print('DATAFLOW already enabled')
        return 0
    if COMMENT not in text:
        print('WARN: v14 DATAFLOW comment not found', file=sys.stderr)
        return 1
    text = text.replace(COMMENT + '\n', PRAGMA + '\n', 1)
    MYPROJECT.write_text(text, encoding='utf-8')
    print('restored top-level DATAFLOW in myproject.cpp')
    return 0


if __name__ == '__main__':
    sys.exit(main())
