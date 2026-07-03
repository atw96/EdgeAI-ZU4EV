#!/usr/bin/env python3
"""Abort Vivado flow if HLS csynth exceeds device LUT/BRAM budget."""
import json
import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEFAULT_RPT = (
    REPO / 'notebooks' / 'hls4ml_prj' / 'myproject_prj' / 'solution1'
    / 'syn' / 'report' / 'myproject_axi_csynth.rpt'
)
OUT = REPO / 'results' / 'hls_csynth_gate.json'

# ZU4EV device limits (same as csynth Available row)
LIMITS = {
    'LUT': int(os.environ.get('HLS_DEVICE_LUT', '87840')),
    'FF': int(os.environ.get('HLS_DEVICE_FF', '175680')),
    'BRAM_18K': int(os.environ.get('HLS_DEVICE_BRAM', '256')),
    'DSP48E': int(os.environ.get('HLS_DEVICE_DSP', '728')),
}
MAX_LUT_PCT = float(os.environ.get('HLS_LUT_MAX_PCT', '95'))


def parse_report(path: Path) -> dict:
    text = path.read_text(encoding='utf-8', errors='replace')
    m = re.search(
        r'\|Total\s+\|\s+(\d+)\|\s+(\d+)\|\s+(\d+)\|\s+(\d+)\|',
        text,
    )
    if not m:
        raise RuntimeError('Total utilization row not found in %s' % path)
    bram, dsp, ff, lut = map(int, m.groups())
    return {
        'BRAM_18K': bram,
        'DSP48E': dsp,
        'FF': ff,
        'LUT': lut,
    }


def main() -> int:
    rpt = Path(os.environ.get('HLS_CSYNTH_RPT', str(DEFAULT_RPT)))
    if not rpt.is_file():
        print('ERROR: missing csynth report %s' % rpt, file=sys.stderr)
        return 2
    used = parse_report(rpt)
    pct = {k: 100.0 * used[k] / LIMITS[k] for k in used}
    bram_pass = used['BRAM_18K'] < LIMITS['BRAM_18K']
    lut_pass = used['LUT'] < LIMITS['LUT']
    ff_pass = used['FF'] < LIMITS['FF']
    pct_pass = all(pct[k] <= MAX_LUT_PCT for k in ('LUT', 'BRAM_18K', 'FF'))
    passed = pct_pass
    result = {
        'passed': passed,
        'bram_pass': bram_pass,
        'lut_pass': lut_pass,
        'ff_pass': ff_pass,
        'placement_pass': bram_pass,
        'used': used,
        'limits': LIMITS,
        'util_pct': {k: round(v, 2) for k, v in pct.items()},
        'max_pct_allowed': MAX_LUT_PCT,
        'source_report': str(rpt),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print('Wrote %s' % OUT)
    for k in ('LUT', 'FF', 'BRAM_18K', 'DSP48E'):
        print('  %s: %d / %d (%.1f%%)' % (k, used[k], LIMITS[k], pct[k]))
    if not passed:
        print(
            'GATE FAIL: utilization exceeds %.0f%% — fix RF/partition before export'
            % MAX_LUT_PCT,
            file=sys.stderr,
        )
        return 1
    print('GATE PASS')
    return 0


if __name__ == '__main__':
    sys.exit(main())
