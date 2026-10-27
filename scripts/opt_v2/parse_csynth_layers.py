#!/usr/bin/env python3
"""Parse Vivado HLS 2020.1 csynth reports for per-layer latency and IndexLoop/ReuseLoop.

2026-10-17: hls_metrics.py only reads the top myproject_axi report. v2 P0 needs the
loop sub-table (IndexLoop iteration latency, pipelined flag) to test hypothesis H1.
"""
import argparse
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DEFAULT_REPORT_DIR = (
    REPO / 'notebooks' / 'hls4ml_prj' / 'myproject_prj' / 'solution1' / 'syn' / 'report'
)
LAYER_NAMES = ('conv1a', 'conv1b', 'conv2a', 'conv2b', 'conv3a', 'conv3b', 'gap')

LATENCY_RE = re.compile(
    r'\|\s+(\d+)\|\s+(\d+)\|\s+([\d.]+)\s*(ns|us|ms|sec)?\s*\|'
    r'\s+([\d.]+)\s*(ns|us|ms|sec)?\s*\|\s+(\d+)\|\s+(\d+)\|'
    r'(?:\s*([A-Za-z_]+)\s*\|)?'
)


def _ints(text):
    return [int(x) for x in re.findall(r'-?\d+', text)]


def parse_loop_line(line):
    if 'IndexLoop' not in line and 'ReuseLoop' not in line:
        return None
    name = 'IndexLoop' if 'IndexLoop' in line else 'ReuseLoop'
    cells = [c.strip() for c in line.split('|') if c.strip()]
    pipelined = None
    numbers = []
    for cell in cells[1:]:
        low = cell.lower()
        if low in ('yes', 'no'):
            pipelined = low == 'yes'
            continue
        numbers.extend(_ints(cell))
    info = {
        'name': name,
        'numbers': numbers,
        'pipelined': pipelined,
        'raw': line.strip(),
    }
    if len(numbers) >= 2:
        info['latency_min'] = numbers[0]
        info['latency_max'] = numbers[1]
    if len(numbers) >= 3:
        info['iteration_latency'] = numbers[2]
    if len(numbers) >= 6:
        info['iteration_latency'] = numbers[2]
        info['ii_achieved'] = numbers[3]
        info['ii_target'] = numbers[4]
        info['trip_count'] = numbers[5]
    elif numbers:
        info['trip_count'] = numbers[-1]
    return info


def parse_report_text(text):
    latency = {}
    match = LATENCY_RE.search(text)
    if match:
        latency = {
            'latency_min_cycles': int(match.group(1)),
            'latency_max_cycles': int(match.group(2)),
            'latency_min_abs': float(match.group(3)),
            'latency_min_unit': match.group(4) or '',
            'latency_max_abs': float(match.group(5)),
            'latency_max_unit': match.group(6) or '',
            'ii_min_cycles': int(match.group(7)),
            'ii_max_cycles': int(match.group(8)),
            'pipeline_type': match.group(9),
        }
    if 'dataflow' in text.lower() and not latency.get('pipeline_type'):
        latency['pipeline_type_hint'] = 'dataflow'
    loops = []
    for line in text.splitlines():
        parsed = parse_loop_line(line)
        if parsed:
            loops.append(parsed)
    util = {}
    util_match = re.search(
        r'\|Total\s+\|\s+(\d+)\|\s+(\d+)\|\s+(\d+)\|\s+(\d+)\|',
        text,
    )
    if util_match:
        bram, dsp, ff, lut = map(int, util_match.groups())
        util = {'BRAM_18K': bram, 'DSP48E': dsp, 'FF': ff, 'LUT': lut}
    return {'latency': latency, 'loops': loops, 'util': util}


def parse_report_dir(report_dir):
    report_dir = Path(report_dir)
    reports = {}
    if not report_dir.is_dir():
        return {'report_dir': str(report_dir), 'missing': True, 'reports': {}}
    for path in sorted(report_dir.glob('*_csynth.rpt')):
        text = path.read_text(encoding='utf-8', errors='replace')
        reports[path.name] = parse_report_text(text)
        reports[path.name]['path'] = str(path)
    return {'report_dir': str(report_dir), 'missing': False, 'reports': reports}


def loops_for_layer(parsed, layer):
    """Collect IndexLoop/ReuseLoop rows whose report name or body mentions the layer."""
    found = []
    for name, body in parsed.get('reports', {}).items():
        blob = name + '\n' + json.dumps(body.get('loops', []))
        if layer not in name and layer not in blob and layer not in json.dumps(body)[:2000]:
            # Still keep loops from any report; association is best-effort below.
            pass
        for loop in body.get('loops', []):
            item = dict(loop)
            item['report'] = name
            if layer in name:
                item['layer_match'] = layer
            found.append(item)
    return found


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--report-dir', default=str(DEFAULT_REPORT_DIR))
    ap.add_argument('--out', default='')
    args = ap.parse_args()
    parsed = parse_report_dir(args.report_dir)
    text = json.dumps(parsed, indent=2)
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding='utf-8')
        print('Wrote', out)
    else:
        print(text)
    return 0 if not parsed.get('missing') else 2


if __name__ == '__main__':
    raise SystemExit(main())
