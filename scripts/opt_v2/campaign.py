#!/usr/bin/env python3
"""Stop/go rules for v2 after each recorded variant. Does not launch Vivado by itself.

Reads results/p0_diag.json and results/opt_v2/*.json. Prints the next allowed
variant or a stop reason. Exit 0 means the printed variant may be built.
Exit 2 means stop.
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DIAG = REPO / 'results' / 'p0_diag.json'
OUT_DIR = REPO / 'results' / 'opt_v2'
ORDER = ('A1prime', 'A2-L', 'A2-M', 'A2-H')
NEXT_SUM_P = {'A1prime': 120, 'A2-L': 188, 'A2-M': 324, 'A2-H': 452}
RED = {'LUT': 60000, 'DSP': 500, 'BRAM': 160}


def _load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def _latest(variant):
    files = sorted(OUT_DIR.glob('%s_*.json' % variant))
    files = [p for p in files if 'fpga_latency' not in p.name and 'correct_' not in p.name]
    return _load(files[-1]) if files else None


def _median_ms(doc):
    if not doc:
        return None
    block = ((doc.get('latency') or {}).get('reset_each')) or {}
    if isinstance(block, dict) and block.get('median') is not None:
        return float(block['median'])
    return None


def _resources_ok(doc):
    if not doc:
        return True
    lut = doc.get('impl_LUT')
    dsp = doc.get('impl_DSP')
    bram = doc.get('impl_BRAM')
    wns = doc.get('WNS')
    if lut is not None and lut >= RED['LUT']:
        return False
    if dsp is not None and dsp >= RED['DSP']:
        return False
    if bram is not None and bram >= RED['BRAM']:
        return False
    if wns is not None and wns < 0:
        return False
    return True


def main():
    if not DIAG.is_file():
        print('stop: missing %s (run p0_diag.py first)' % DIAG)
        return 2
    diag = _load(DIAG)
    verdict = diag.get('verdict')
    if verdict not in ('proceed_a1prime', 'restore_dataflow_then_a1prime'):
        print('stop: p0 verdict=%s' % verdict)
        return 2

    prev_name = None
    prev_ms = None
    for name in ORDER:
        doc = _latest(name)
        if doc is None:
            if prev_name is not None:
                if prev_ms is None:
                    print('stop: %s has no board median; do not start %s' % (prev_name, name))
                    return 2
                if not _resources_ok(_latest(prev_name)):
                    print('stop: %s hit a resource or timing red line' % prev_name)
                    return 2
            print('next=%s p0=%s' % (name, verdict))
            return 0
        if not _resources_ok(doc):
            print('stop: %s resources' % name)
            return 2
        util = doc.get('csynth_util') or {}
        lut = util.get('LUT')
        bram = util.get('BRAM_18K')
        if (lut is not None and lut > 87840) or (bram is not None and bram > 256):
            print('stop: %s csynth exceeds the device LUT=%s BRAM_18K=%s; impl not allowed' % (name, lut, bram))
            return 2
        ms = _median_ms(doc)
        if prev_ms is not None and ms is not None:
            drop = (prev_ms - ms) / prev_ms
            if drop < 0.15:
                print('stop: %s latency drop %.1f%% < 15%%' % (name, 100.0 * drop))
                return 2
        prev_name = name
        if ms is not None:
            prev_ms = ms

    final_ms = _median_ms(_latest('A2-H')) or _median_ms(_latest('A2-M')) or _median_ms(_latest('A2-L')) or _median_ms(_latest('A1prime'))
    if final_ms is None:
        print('stop: no board median yet')
        return 2
    if final_ms > 2.0:
        print('stop: board median %.3f ms > 2 ms, do not start line B' % final_ms)
        return 2
    print('next=B1 board_median_ms=%.3f' % final_ms)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
