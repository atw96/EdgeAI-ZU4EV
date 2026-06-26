#!/usr/bin/env python3
"""Parse axis32 board_diagnose log; exit 0 if mid4 non-zero (success)."""
import json
import re
import sys
from pathlib import Path


def parse_board_log(text):
    mid4 = None
    zeros = None
    raw20 = None
    m = re.search(r'mid4 int16:\s*\[([^\]]+)\]', text)
    if m:
        mid4 = [int(x.strip()) for x in m.group(1).split(',')]
    m = re.search(r'zeros at 4-7:\s*(True|False)', text)
    if m:
        zeros = m.group(1) == 'True'
    m = re.search(r'raw20 hex:\s*([0-9a-f]+)', text)
    if m:
        raw20 = m.group(1)
    return {'mid4': mid4, 'zeros_at_4_7': zeros, 'raw20_hex': raw20}


def main():
    log_path = Path(sys.argv[1] if len(sys.argv) > 1 else 'results/axis32_out_board.log')
    if not log_path.is_file():
        out = {'success': False, 'reason': 'missing_board_log', 'path': str(log_path)}
        print(json.dumps(out, indent=2))
        return 2
    text = log_path.read_text(encoding='utf-8', errors='replace')
    parsed = parse_board_log(text)
    mid4 = parsed.get('mid4')
    success = bool(mid4) and not all(v == 0 for v in mid4)
    out = {
        'success': success,
        'mid4': mid4,
        'zeros_at_4_7': parsed.get('zeros_at_4_7'),
        'raw20_hex': parsed.get('raw20_hex'),
    }
    print(json.dumps(out, indent=2))
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
