#!/usr/bin/env python3
"""Assemble results/p0_diag.json for optimization plan v2 stage 0.

Does not change RF or bit width. Exit codes:
  0  H1 and/or H2 supported — A1' is allowed (H2 still means restore DATAFLOW first)
  2  H4 clock is not 200 MHz — do not lower RF
  3  H1/H2/H4 all rejected — stop and return this JSON
  4  evidence incomplete — do not lower RF
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'scripts'))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from parse_csynth_layers import parse_report_dir  # noqa: E402
from rf_planner import dense_variant, layers as planner_layers  # noqa: E402
from v19_hls_config_common import RF_PER_LAYER  # noqa: E402

OUT_DEFAULT = REPO / 'results' / 'p0_diag.json'
HLS = REPO / 'notebooks' / 'hls4ml_prj'
REPORT_DIR = HLS / 'myproject_prj' / 'solution1' / 'syn' / 'report'
HWH = REPO / 'deploy' / 'cifar10_accel.hwh'
CONV_NAMES = ('conv1a', 'conv1b', 'conv2a', 'conv2b', 'conv3a', 'conv3b')


def _clocks_from_hwh(path):
    if not path.is_file():
        return []
    text = path.read_text(encoding='utf-8', errors='replace')
    # VALUE="199998001" is the 200 MHz PLL. Ignore the "..._d" decimal 199.998001.
    values = [int(x) for x in re.findall(r'FREQ_HZ"\s+VALUE="(\d+)"', text)]
    return sorted(set(values))


def _is_200mhz(hz):
    if not hz:
        return False
    return abs(int(hz) - 200_000_000) / 200_000_000.0 < 0.01


def _pick_pl_clock(clocks):
    near = [hz for hz in clocks if _is_200mhz(hz)]
    if near:
        return near[0]
    return clocks[0] if clocks else None


def _has_dataflow(hls_root):
    hits = []
    firmware = hls_root / 'firmware'
    if not firmware.is_dir():
        return {'present': None, 'hits': [], 'removed_comment': False}
    removed = False
    for path in sorted(firmware.glob('*.cpp')):
        text = path.read_text(encoding='utf-8', errors='replace')
        for i, line in enumerate(text.splitlines(), 1):
            if 'DATAFLOW' in line:
                try:
                    rel = str(path.relative_to(REPO))
                except ValueError:
                    rel = str(path)
                hits.append({'file': rel, 'line': i, 'text': line.strip()})
            if 'DATAFLOW removed' in line:
                removed = True
    pragma = any('#pragma HLS DATAFLOW' in h['text'] for h in hits)
    return {'present': pragma, 'hits': hits, 'removed_comment': removed}


def _diff_nnet_utils(hls_root):
    try:
        import hls4ml
        import os
        template = Path(os.path.dirname(hls4ml.__file__)) / 'templates' / 'vivado' / 'nnet_utils'
    except Exception as exc:
        return {'empty': None, 'error': 'hls4ml import failed: %s' % exc}
    local = Path(hls_root) / 'firmware' / 'nnet_utils'
    if not template.is_dir() or not local.is_dir():
        return {
            'empty': None,
            'error': 'missing template or local nnet_utils',
            'template': str(template),
            'local': str(local),
        }
    proc = subprocess.run(
        ['diff', '-rq', str(template), str(local)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True,
    )
    lines = [ln for ln in proc.stdout.splitlines() if ln.strip()]
    return {
        'empty': proc.returncode == 0 and not lines,
        'returncode': proc.returncode,
        'diff_lines': lines[:80],
        'template': str(template),
        'local': str(local),
    }


def _theory():
    by_name = {row['name']: row for row in planner_layers()}
    rows = []
    for name in CONV_NAMES:
        rf = int(RF_PER_LAYER[name])
        layer = by_name[name]
        cycles = layer['px'] * rf
        rows.append({
            'name': name,
            'rf': rf,
            'n_in': layer['n_in'],
            'n_out': layer['n_out'],
            'px': layer['px'],
            'theory_px_x_rf': cycles,
            'branch': dense_variant(layer['n_in'], rf),
            'P': layer['n_in'] * layer['n_out'] // rf,
        })
    return rows


def _top_report(parsed):
    reports = parsed.get('reports') or {}
    for key in ('myproject_axi_csynth.rpt',):
        if key in reports:
            return reports[key]
    for key, body in reports.items():
        if 'myproject_axi' in key:
            return body
    return None


def _reuse_loops(parsed):
    """IndexLoop is often inlined into ReuseLoop. The report name records the branch."""
    found = []
    for name, body in (parsed.get('reports') or {}).items():
        for loop in body.get('loops') or []:
            if loop.get('name') not in ('IndexLoop', 'ReuseLoop'):
                continue
            item = dict(loop)
            item['report'] = name
            if 'rf_gt_nin_rem0' in name:
                item['branch'] = 'rf_gt_nin_rem0'
            elif 'rf_leq_nin' in name:
                item['branch'] = 'rf_leq_nin'
            elif 'rf_gt_nin' in name:
                item['branch'] = 'rf_gt_nin'
            found.append(item)
    return found


def _judge(doc):
    """Fill doc['verdict'] and return a process exit code."""
    clock = doc.get('pl_clock_hz')
    h4 = None
    if clock and not _is_200mhz(clock) and doc.get('clock_source') == 'board':
        h4 = True
    elif clock and not _is_200mhz(clock):
        h4 = True
    elif clock and _is_200mhz(clock):
        h4 = False
    dataflow = doc.get('has_dataflow')
    h2_source = None if dataflow is None else (not dataflow)
    top = doc.get('top') or {}
    lat = top.get('latency_max_cycles')
    ii = top.get('ii_max_cycles')
    h2_interval = None
    if lat and ii:
        h2_interval = abs(ii - lat) / float(lat) < 0.05
    h2 = None
    if h2_source or h2_interval:
        h2 = True
    elif h2_source is False and h2_interval is False:
        h2 = False

    ratios = [row.get('ratio') for row in doc['layers'] if row.get('ratio') is not None]
    index_loops = doc.get('indexloop') or []
    slow_reuse = [
        row for row in doc['layers']
        if row.get('branch') == 'rf_gt_nin_rem0' and (row.get('reuse_ii_achieved') or 1) > 1
    ]
    h1 = None
    if index_loops:
        slow = [
            loop for loop in index_loops
            if (loop.get('iteration_latency') or 0) >= 6 and loop.get('pipelined') is False
        ]
        h1 = bool(slow) or bool(slow_reuse)
    elif slow_reuse:
        # IndexLoop was inlined; ReuseLoop target II is 1 but achieved II is 8..15.
        h1 = True
    elif ratios and all(7.0 <= r <= 11.0 for r in ratios):
        h1 = True
    elif ratios:
        h1 = False

    if not doc.get('csynth_present'):
        action = 'incomplete_no_csynth'
        code = 4
    elif h4:
        action = 'stop_fix_clock'
        code = 2
    elif h1 is None and h2 is None:
        action = 'incomplete'
        code = 4
    elif h1 or h2:
        if h2_source:
            action = 'restore_dataflow_then_a1prime'
        else:
            action = 'proceed_a1prime'
        code = 0
    else:
        action = 'stop_all_hypotheses_rejected'
        code = 3

    doc['hypotheses'] = {
        'H1_indexloop_unpipelined': h1,
        'H2_no_dataflow_or_serial_interval': h2,
        'H2_source_missing_pragma': h2_source,
        'H2_interval_approx_latency': h2_interval,
        'H4_clock_not_200mhz': h4,
    }
    doc['verdict'] = action
    return code


def build(report_dir, board_clk, hls_root):
    theory = _theory()
    parsed = parse_report_dir(report_dir)
    clocks = _clocks_from_hwh(HWH)
    if board_clk:
        pl_clock = int(board_clk)
        clock_source = 'board'
    elif _pick_pl_clock(clocks) and _is_200mhz(_pick_pl_clock(clocks)):
        pl_clock = _pick_pl_clock(clocks)
        clock_source = 'hwh'
    elif clocks:
        pl_clock = clocks[0]
        clock_source = 'hwh'
    else:
        pl_clock = None
        clock_source = None

    top_body = _top_report(parsed) or {}
    top_lat = (top_body.get('latency') or {})
    reuse_loops = _reuse_loops(parsed)
    by_trip = {}
    for loop in reuse_loops:
        if loop.get('name') == 'ReuseLoop' and loop.get('trip_count') is not None:
            by_trip[int(loop['trip_count'])] = loop
    index_loops = [loop for loop in reuse_loops if loop.get('name') == 'IndexLoop']
    iter_lats = [
        loop.get('iteration_latency') for loop in index_loops
        if loop.get('iteration_latency') is not None
    ]
    reuse_iter_lats = [
        loop.get('iteration_latency') for loop in by_trip.values()
        if loop.get('iteration_latency') is not None
    ]

    layers = []
    for row in theory:
        loop = by_trip.get(int(row['rf']))
        cycles = None
        ratio = None
        if loop and loop.get('iteration_latency'):
            cycles = int(row['px']) * int(loop['trip_count']) * int(loop['iteration_latency'])
            ratio = round(float(loop['iteration_latency']), 4)
        layers.append(dict(
            row,
            csynth_latency_cycles=cycles,
            ratio=ratio,
            reuse_iteration_latency=None if not loop else loop.get('iteration_latency'),
            reuse_ii_achieved=None if not loop else loop.get('ii_achieved'),
            reuse_ii_target=None if not loop else loop.get('ii_target'),
            reuse_pipelined=None if not loop else loop.get('pipelined'),
            reuse_report=None if not loop else loop.get('report'),
        ))

    dataflow = _has_dataflow(hls_root)
    diff = _diff_nnet_utils(hls_root)
    doc = {
        'pl_clock_hz': pl_clock,
        'clock_source': clock_source,
        'hwh_freq_hz': clocks,
        'layers': layers,
        'theory_sum_cycles': sum(row['theory_px_x_rf'] for row in theory),
        'theory_max_cycles': max(row['theory_px_x_rf'] for row in theory),
        'has_dataflow': dataflow['present'],
        'dataflow_detail': dataflow,
        'indexloop_iter_latency': iter_lats or reuse_iter_lats,
        'indexloop': index_loops,
        'reuse_loops': list(by_trip.values()),
        'notes': [
            'ReuseLoop trip count is matched to each layer RF.',
            'A missing IndexLoop with ReuseLoop iteration latency near 8 means the IndexLoop was inlined.',
        ],
        'diff_nnet_utils_empty': diff.get('empty'),
        'diff_nnet_utils': diff,
        'csynth_present': not parsed.get('missing') and bool(parsed.get('reports')),
        'top': top_lat,
        'rf_table': {name: int(RF_PER_LAYER[name]) for name in CONV_NAMES},
        'global_rf_min': int(min(RF_PER_LAYER.values())),
    }
    if top_lat.get('latency_max_cycles') and doc['theory_sum_cycles']:
        doc['top_ratio_vs_sum'] = round(
            top_lat['latency_max_cycles'] / float(doc['theory_sum_cycles']), 4,
        )
    return doc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--report-dir', default=str(REPORT_DIR))
    ap.add_argument('--out', default=str(OUT_DEFAULT))
    ap.add_argument('--board-clk-hz', type=int, default=0)
    ap.add_argument('--hls-root', default=str(HLS))
    ap.add_argument('--force', action='store_true')
    args = ap.parse_args()
    doc = build(args.report_dir, args.board_clk_hz or None, Path(args.hls_root))
    code = _judge(doc)
    out = Path(args.out)
    if out.exists() and not args.force:
        # Do not overwrite an existing diagnosis; keep the new one beside it.
        stamped = out.with_name(out.stem + '_new' + out.suffix)
        if stamped.exists():
            print('ERROR: refuse to overwrite %s' % stamped, file=sys.stderr)
            return 5
        print('NOTE: %s exists; writing %s' % (out, stamped))
        out = stamped
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2), encoding='utf-8')
    print('Wrote %s verdict=%s exit=%d' % (out, doc['verdict'], code))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
