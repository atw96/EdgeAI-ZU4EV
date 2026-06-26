#!/usr/bin/env python3
"""v14: remove top-level DATAFLOW to cut LUT/BRAM (layers run sequentially)."""
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
    if COMMENT in text:
        print('DATAFLOW already removed')
        return 0
    if PRAGMA not in text:
        print('WARN: DATAFLOW pragma not found', file=sys.stderr)
        return 1
    text = text.replace(PRAGMA, COMMENT + '\n', 1)
    MYPROJECT.write_text(text, encoding='utf-8')
    print('removed top-level DATAFLOW from myproject.cpp')
    return 0


if __name__ == '__main__':
    sys.exit(main())
