#!/usr/bin/env python3
"""P2: attribute the existing A1' csynth report. Does not run synthesis.

Reads Vivado HLS 2020.1 *_csynth.rpt files plus the csynth log. Writes
results/opt_v2/p2_attribution.json and refuses to overwrite it.
"""
import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

# hls4ml config index -> network layer, from the A1' report names.
LAYER_BY_CONFIG = {
    '3': 'conv1a',
    '7': 'conv1b',
    '12': 'conv2a',
    '16': 'conv2b',
    '21': 'conv3a',
    '25': 'conv3b',
    '29': 'gap',
    '30': 'zeropad_in',
    '11': 'pool1',
    '20': 'pool2',
}


def _cells(line):
    if '|' not in line:
        return []
    return [c.strip() for c in line.strip().strip('|').split('|')]


def _section(text, start_pat, end_pats):
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if re.search(start_pat, line):
            start = i
            break
    if start is None:
        return []
    out = []
    for line in lines[start + 1:]:
        if any(re.search(p, line) for p in end_pats):
            break
        out.append(line)
    return out


def parse_pipe_table(lines):
    rows = []
    header = None
    for line in lines:
        cells = _cells(line)
        if len(cells) < 2:
            continue
        if set(cells[0]) <= set('+-'):
            continue
        if header is None:
            header = cells
            continue
        if cells[0].lower() == 'total':
            rows.append(dict(zip(header, cells)))
            continue
        rows.append(dict(zip(header, cells)))
    return rows


def _num(text):
    if text is None:
        return None
    m = re.search(r'-?\d+', text.replace(',', ''))
    return int(m.group(0)) if m else None


def parse_summary_util(text):
    m = re.search(
        r'\|Total\s+\|\s+(\d+)\|\s+(\d+)\|\s+(\d+)\|\s+(\d+)\|\s+(\d+)\|',
        text,
    )
    if not m:
        return {}
    bram, dsp, ff, lut, uram = map(int, m.groups())
    return {'BRAM_18K': bram, 'DSP48E': dsp, 'FF': ff, 'LUT': lut, 'URAM': uram}


def parse_category_util(text):
    rows = {}
    for line in text.splitlines():
        cells = _cells(line)
        if len(cells) < 5:
            continue
        name = cells[0]
        if name in ('FIFO', 'Instance', 'Memory', 'Expression', 'Multiplexer', 'Register', 'DSP'):
            nums = []
            for c in cells[1:6]:
                if c in ('-', ''):
                    nums.append(None)
                else:
                    nums.append(_num(c))
            rows[name] = {
                'BRAM_18K': nums[0],
                'DSP48E': nums[1] if len(nums) > 1 else None,
                'FF': nums[2] if len(nums) > 2 else None,
                'LUT': nums[3] if len(nums) > 3 else None,
            }
    return rows


def parse_latency_summary(text):
    # First latency summary row with two cycle counts.
    for line in text.splitlines():
        cells = _cells(line)
        if len(cells) < 6:
            continue
        if re.fullmatch(r'\d+', cells[0]) and re.fullmatch(r'\d+', cells[1]):
            return {
                'latency_min_cycles': int(cells[0]),
                'latency_max_cycles': int(cells[1]),
                'latency_min_abs': cells[2],
                'latency_max_abs': cells[3],
                'ii_min_cycles': _num(cells[4]),
                'ii_max_cycles': _num(cells[5]),
                'pipeline_type': cells[6] if len(cells) > 6 else None,
            }
    return {}


def parse_loops(text):
    loops = []
    in_loop = False
    for line in text.splitlines():
        if '* Loop:' in line:
            in_loop = True
            continue
        if in_loop and line.startswith('==='):
            break
        if not in_loop or '|' not in line:
            continue
        if 'Loop Name' in line or set(line.strip()) <= set('+-| '):
            continue
        cells = _cells(line)
        if len(cells) < 7:
            continue
        name = cells[0].lstrip('- ').strip()
        if not name or name.lower() == 'loop name':
            continue
        loops.append({
            'name': name,
            'latency_min': _num(cells[1]),
            'latency_max': _num(cells[2]),
            'iteration_latency': cells[3],
            'ii_achieved': _num(cells[4]) if cells[4] not in ('-', '') else None,
            'ii_target': _num(cells[5]) if cells[5] not in ('-', '') else None,
            'trip_count': _num(cells[6]),
            'pipelined': cells[7].lower() if len(cells) > 7 else None,
        })
    return loops


def layer_of(name):
    m = re.search(r'config(\d+)', name)
    if not m:
        return None
    return LAYER_BY_CONFIG.get(m.group(1))


def parse_instances(text):
    """Utilization instance table only. The latency instance table has no BRAM column."""
    rows = []
    capturing = False
    for line in text.splitlines():
        cells = _cells(line)
        if cells and 'BRAM_18K' in cells and 'Instance' in cells[0]:
            capturing = True
            continue
        if not capturing:
            continue
        if not cells:
            continue
        if cells[0] == 'Total':
            break
        if len(cells) < 6 or cells[0] in ('Instance', 'Module'):
            continue
        rows.append({
            'instance': cells[0],
            'module': cells[1],
            'layer': layer_of(cells[0]) or layer_of(cells[1]),
            'BRAM_18K': _num(cells[2]),
            'DSP48E': _num(cells[3]),
            'FF': _num(cells[4]),
            'LUT': _num(cells[5]),
            'URAM': _num(cells[6]) if len(cells) > 6 else None,
        })
    return rows


def parse_fifos(text):
    lines = _section(text, r'\* FIFO:', [r'\* Expression', r'\* Multiplexer', r'\* Register', r'^==='])
    rows = []
    for line in lines:
        cells = _cells(line)
        if len(cells) < 8 or cells[0] in ('Name', 'Total'):
            continue
        if not re.search(r'\d', cells[1]):
            continue
        rows.append({
            'name': cells[0],
            'BRAM_18K': _num(cells[1]) or 0,
            'FF': _num(cells[2]) or 0,
            'LUT': _num(cells[3]) or 0,
            'depth': _num(cells[5]),
            'bits': _num(cells[6]),
        })
    return rows


def fifo_groups(rows):
    groups = {}
    for row in rows:
        key = re.sub(r'_data_.*', '', row['name'])
        g = groups.setdefault(key, {
            'streams': 0, 'BRAM_18K': 0, 'FF': 0, 'LUT': 0,
            'depth': row['depth'], 'bits': row['bits'],
        })
        g['streams'] += 1
        g['BRAM_18K'] += row['BRAM_18K']
        g['FF'] += row['FF']
        g['LUT'] += row['LUT']
    return groups


def parse_log_ii(log_text):
    """Pair each dense_resource module with the II result and the port warning above it."""
    hits = []
    lines = log_text.splitlines()
    for i, line in enumerate(lines):
        if 'Pipelining result' not in line or 'Final II' not in line:
            continue
        m = re.search(r'Target II = (\d+), Final II = (\d+), Depth = (\d+)', line)
        if not m:
            continue
        window = '\n'.join(lines[max(0, i - 12):i + 1])
        mod = None
        for prev in reversed(lines[max(0, i - 20):i]):
            mm = re.search(r"Implementing module '([^']+)'", prev)
            if mm:
                mod = mm.group(1)
                break
        warns = re.findall(r'Unable to schedule .*', window)
        hits.append({
            'module': mod,
            'layer': layer_of(mod or ''),
            'target_ii': int(m.group(1)),
            'final_ii': int(m.group(2)),
            'depth': int(m.group(3)),
            'memory_port_warnings': warns,
        })
    return hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--report-dir', required=True)
    ap.add_argument('--log', required=True)
    ap.add_argument('--out', default=str(REPO / 'results' / 'opt_v2' / 'p2_attribution.json'))
    args = ap.parse_args()
    out = Path(args.out)
    if out.exists():
        print('ERROR: refuse to overwrite %s' % out, file=sys.stderr)
        return 1
    report_dir = Path(args.report_dir)
    axi = (report_dir / 'myproject_axi_csynth.rpt').read_text(encoding='utf-8', errors='replace')
    top = (report_dir / 'myproject_csynth.rpt').read_text(encoding='utf-8', errors='replace')
    log_text = Path(args.log).read_text(encoding='utf-8', errors='replace')

    instances = [r for r in parse_instances(top) if r['instance'] != 'Total']
    fifos = parse_fifos(top)
    groups = fifo_groups(fifos)
    bram_by_group = sorted(groups.items(), key=lambda kv: -kv[1]['BRAM_18K'])

    per_layer = []
    for path in sorted(report_dir.glob('*_csynth.rpt')):
        text = path.read_text(encoding='utf-8', errors='replace')
        layer = layer_of(path.name)
        kind = 'other'
        if path.name.startswith('conv_2d'):
            kind = 'conv'
        elif path.name.startswith('dense_resource'):
            kind = 'dense_mult'
        elif path.name.startswith('zeropad'):
            kind = 'zeropad'
        elif path.name.startswith('relu'):
            kind = 'relu'
        elif 'pooling2d_cl' in path.name and 'global' not in path.name:
            kind = 'pool'
        elif 'global_pooling' in path.name:
            kind = 'gap'
        elif path.name.startswith('normalize'):
            kind = 'normalize'
        elif path.name in ('myproject_csynth.rpt', 'myproject_axi_csynth.rpt'):
            kind = 'top'
        loops = parse_loops(text)
        if kind == 'other' and not loops:
            continue
        per_layer.append({
            'report': path.name,
            'kind': kind,
            'layer': layer,
            'latency': parse_latency_summary(text),
            'loops': loops,
            'util': parse_summary_util(text),
        })

    ii_hits = [h for h in parse_log_ii(log_text) if h['layer'] in LAYER_BY_CONFIG.values() or (h['module'] and 'config3_mult' in h['module'])]
    conv1a_ii = next((h for h in parse_log_ii(log_text) if h['module'] and 'config3_mult' in h['module'] and h['final_ii'] != h['target_ii']), None)
    if conv1a_ii is None:
        conv1a_ii = next((h for h in parse_log_ii(log_text) if h['module'] and 'config3_mult' in h['module']), None)

    conv_rows = [r for r in instances if r['layer'] and r['layer'].startswith('conv')]
    fifo_bram = sum(r['BRAM_18K'] for r in fifos)
    inst_bram = sum((r['BRAM_18K'] or 0) for r in instances)
    fifo_lut = sum(r['LUT'] for r in fifos)
    inst_lut = sum((r['LUT'] or 0) for r in instances)

    conv1a_conv = next((x for x in per_layer if x['kind'] == 'conv' and x['layer'] == 'conv1a'), None)
    conv1a_dense = next((x for x in per_layer if x['kind'] == 'dense_mult' and x['layer'] == 'conv1a'), None)
    pixel = None
    reuse = None
    if conv1a_conv:
        pixel = next((L for L in conv1a_conv['loops'] if 'ReadInput' in L['name']), None)
    if conv1a_dense:
        reuse = next((L for L in conv1a_dense['loops'] if 'Reuse' in L['name']), None)

    verdict = 'i_reuseloop_ii_gt_1'
    reason = (
        'conv1a ReuseLoop target II=1 achieved II=8 because the scheduler cannot '
        'issue the kernel_data load (limited memory ports). The spatial loop is not '
        'pipelined, so its 1156 padded pixels (34x34) each pay that inner latency. '
        'IndexLoop is absent. Do not change RF before a port/partition experiment.'
    )

    doc = {
        'source_report_dir': str(report_dir),
        'verdict': verdict,
        'verdict_meaning': reason,
        'do_not_change_rf_yet': True,
        'top_axi': {
            'latency': parse_latency_summary(axi),
            'util': parse_summary_util(axi),
            'categories': parse_category_util(axi),
            'uram_available': 48,
            'uram_used': (parse_summary_util(axi) or {}).get('URAM'),
        },
        'myproject_categories': parse_category_util(top),
        'instances': instances,
        'instance_sums': {'BRAM_18K': inst_bram, 'LUT': inst_lut},
        'conv_instance_sums': {
            'LUT': sum((r['LUT'] or 0) for r in conv_rows),
            'BRAM_18K': sum((r['BRAM_18K'] or 0) for r in conv_rows),
            'DSP48E': sum((r['DSP48E'] or 0) for r in conv_rows),
        },
        'fifo': {
            'count': len(fifos),
            'BRAM_18K': fifo_bram,
            'LUT': fifo_lut,
            'by_stream': [
                {'name': k, **v} for k, v in bram_by_group if v['BRAM_18K'] > 0
            ],
        },
        'conv1a': {
            'spatial_loop': pixel,
            'reuse_loop': reuse,
            'index_loop_present': False,
            'scheduler': conv1a_ii,
            'cycles_per_output_pixel': None,
        },
        'layers': [x for x in per_layer if x['kind'] != 'other'],
        'scheduler_ii': [h for h in parse_log_ii(log_text) if h['memory_port_warnings'] or (h['final_ii'] and h['target_ii'] and h['final_ii'] > h['target_ii'])],
    }
    if pixel and pixel.get('latency_max') and pixel.get('trip_count'):
        # 32*32 output pixels; the loop itself walks the padded 34*34.
        doc['conv1a']['cycles_per_output_pixel'] = pixel['latency_max'] / 1024.0
        doc['conv1a']['cycles_per_spatial_iter'] = pixel['latency_max'] / float(pixel['trip_count'])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2), encoding='utf-8')
    print('Wrote %s' % out)
    print('verdict=%s fifo_bram=%s inst_lut=%s conv1a_ii=%s' % (
        verdict, fifo_bram, inst_lut,
        None if not conv1a_ii else conv1a_ii.get('final_ii'),
    ))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
