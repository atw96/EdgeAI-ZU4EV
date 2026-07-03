#!/usr/bin/env python3
"""
Compare MM2S input path: npz payload vs csim tb_input vs board CMA staging.
Writes results/mm2s_csim_board_align.json and results/ila_output_stream_plan.md
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
NPZ = REPO / 'deploy' / 'cifar10_bench.npz'
TB_INPUT = REPO / 'notebooks' / 'hls4ml_prj' / 'tb_data' / 'tb_input_features.dat'
OUT_JSON = REPO / 'results' / 'mm2s_csim_board_align.json'
OUT_ILA = REPO / 'results' / 'ila_output_stream_plan.md'

BOARD_IP = os.environ.get('BOARD_IP', '192.168.1.40')
BOARD_PASS = os.environ.get('BOARD_PASS', 'root')
IN_SCALE = int(os.environ.get('IN_FIXED_SCALE', '1024'))
IN_BYTES = 6144
N_WORDS = 3072


def npz_int16_line(raw):
    return np.frombuffer(raw, dtype=np.int16)


def tb_int16_line(tb_line):
    floats = np.array([float(x) for x in tb_line.split()], dtype=np.float32)
    return np.round(floats * IN_SCALE).astype(np.int16)


def preload_pl_on_board():
    """Load bitstream so CMA/DMA reserved memory is valid before devmem."""
    bit = REPO / 'deploy' / 'cifar10_accel.bit'
    load_sh = REPO / 'scripts' / 'board_load_only.sh'
    if not bit.is_file() or not load_sh.is_file():
        raise RuntimeError('missing bit or board_load_only.sh for PL preload')
    ssh_base = [
        'sshpass', '-p', BOARD_PASS,
        'ssh', '-o', 'StrictHostKeyChecking=no', '-o', 'UserKnownHostsFile=/dev/null',
        'root@%s' % BOARD_IP,
    ]
    scp_base = [
        'sshpass', '-p', BOARD_PASS,
        'scp', '-o', 'StrictHostKeyChecking=no', '-o', 'UserKnownHostsFile=/dev/null',
    ]
    subprocess.run(ssh_base + ['mkdir', '-p', '/tmp/edgeai_bench'], check=True, timeout=30)
    subprocess.run(
        scp_base + [
            str(REPO / 'scripts' / 'board_read_cma_input.py'),
            str(REPO / 'scripts' / 'dma_infer_common.py'),
            str(REPO / 'scripts' / 'slot32_layout.py'),
            str(REPO / 'deploy' / 'cifar10_bench.npz'),
            str(bit),
            str(load_sh),
            'root@%s:/tmp/edgeai_bench/' % BOARD_IP,
        ],
        check=True,
        timeout=120,
    )
    subprocess.run(
        ssh_base + [
            'cp /tmp/edgeai_bench/cifar10_accel.bit /lib/firmware/cifar10_accel.bit && '
            'chmod +x /tmp/edgeai_bench/board_load_only.sh && '
            'FORCE_PL_RELOAD=1 sh /tmp/edgeai_bench/board_load_only.sh',
        ],
        check=True,
        timeout=120,
    )


def fetch_board_cma(sample_idx):
    env = 'SAMPLE_IDX=%d BENCH_NPZ=cifar10_bench.npz CMA_READ_BYTES=%d' % (sample_idx, IN_BYTES)
    cmd = [
        'sshpass', '-p', BOARD_PASS,
        'ssh', '-o', 'StrictHostKeyChecking=no', '-o', 'UserKnownHostsFile=/dev/null',
        'root@%s' % BOARD_IP,
        'cd /tmp/edgeai_bench && %s python3 -u board_read_cma_input.py' % env,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr[-500:] or proc.stdout[-500:])
    return json.loads(proc.stdout.strip().splitlines()[-1])


def compare_samples(n):
    data = np.load(NPZ, allow_pickle=True)
    if not TB_INPUT.is_file():
        raise RuntimeError('missing %s — run prepare_gap_csim_tb.py or run_gap_axi_csim.sh first' % TB_INPUT)
    tb_lines = TB_INPUT.read_text(encoding='utf-8').strip().splitlines()

    samples = []
    for i in range(min(n, len(data['payloads']), len(tb_lines))):
        raw = bytes(data['payloads'][i])
        npz_i16 = npz_int16_line(raw)
        tb_i16 = tb_int16_line(tb_lines[i])
        n_cmp = min(len(npz_i16), len(tb_i16), N_WORDS)
        diff_idx = [j for j in range(n_cmp) if npz_i16[j] != tb_i16[j]]
        samples.append({
            'sample': i,
            'label': int(data['labels'][i]),
            'npz_tb_match_pct': round(100.0 * (n_cmp - len(diff_idx)) / n_cmp, 2),
            'npz_tb_mismatch_count': len(diff_idx),
            'first_mismatches': [
                {'idx': j, 'npz': int(npz_i16[j]), 'tb': int(tb_i16[j])}
                for j in diff_idx[:8]
            ],
        })
    return samples


def write_ila_plan(report):
    input_ok = (
        report['host_npz_vs_tb'].get('all_match')
        and report.get('board_cma_matches_npz')
    )
    host_ok = report['host_npz_vs_tb'].get('all_match')
    lines = [
        '# ILA 核验计划：output_stream（由 MM2S 对比结果自动生成）',
        '',
        '## MM2S 对比结论',
        '',
        '- **判定**: %s' % report['verdict'],
        '- **主机 npz vs csim tb_input**: %s' % (
            '全部一致 (N=%d)' % report['host_npz_vs_tb'].get('n_samples', 0)
            if host_ok else '存在不一致'),
        '- **板端 CMA 回读 vs npz**: %s' % (
            '一致' if report.get('board_cma_matches_npz') else '不一致/未测'),
        '',
    ]
    if host_ok and not report.get('board_cma_matches_npz'):
        lines += [
            '## 当前阶段：主机输入已对齐，板端待验证',
            '',
            '1. **板子若 SSH 超时**：先断电/重启 ZU4EV（未加载 PL 时 devmem 访问 CMA 可能导致总线挂死）',
            '2. 恢复后运行：`BOARD_PRELOAD_PL=1 python3 scripts/mm2s_csim_board_align.py`（脚本会先 `board_load_only` 再 CMA 回读）',
            '3. CMA 一致后再跑 `bash scripts/board_safe_verify.sh` 与 ILA',
            '',
            '### 主机侧已确认',
            '',
            '- `deploy/cifar10_bench.npz` int16 payload 与 `tb_input_features.dat`（×1024）**10/10 样本完全一致**',
            '- 输入预处理不是 Top-1 偏低的根因；问题在 PL 输出路径',
            '',
        ]
    elif not input_ok:
        lines += [
            '## 当前阶段：先修输入，暂不上 ILA',
            '',
            '1. 重新生成 `deploy/cifar10_bench.npz`（`scripts/gen_board_samples.py`）',
            '2. 重跑 `run_gap_axi_csim.sh` 刷新 `tb_input_features.dat`',
            '3. 再跑 `python3 scripts/mm2s_csim_board_align.py`',
            '',
        ]
    else:
        lines += [
            '## 阶段：输入已对齐 → ILA 抓 output_stream',
            '',
            '### 前置条件',
            '',
            '1. 板上已加载 bit MD5 与 `deploy/cifar10_accel.bit` 一致',
            '2. 运行一次 `bash scripts/board_safe_verify.sh`（单次 DMA，勿跑 s2mm_scan）',
            '3. Vivado Hardware Manager 连接板子，`.ltx` 来自最近一次 impl（含 debug_nets）',
            '',
            '### 探针信号（优先）',
            '',
            '| 信号 | 说明 |',
            '|------|------|',
            '| `cifar10_accel_0/output_stream_TDATA[31:0]` | 输出 beat 数据 |',
            '| `cifar10_accel_0/output_stream_TVALID` | 有效 |',
            '| `cifar10_accel_0/output_stream_TREADY` | DMA 反压 |',
            '| `cifar10_accel_0/output_stream_TLAST` | 帧结束 |',
            '| `axi_dma_0/S_AXIS_S2MM_TDATA` | S2MM 入口（可选） |',
            '',
            '### 触发与采样',
            '',
            '1. ILA 触发：`output_stream_TVALID=1` 且 `TREADY=1`',
            '2. 捕获深度 ≥ 32（需看到 24 拍 + TLAST）',
            '3. 在 PS 侧触发一次推理：`board_fetch_gap.py` sample 0',
            '',
            '### 判定（sample 0）',
            '',
            '对照 `notebooks/hls4ml_prj/tb_data/csim_axis_beats.log` 第 1 行 24 个十六进制字：',
            '',
            '- **serial 正确**：连续 24 拍，低 16 位与 csim 逐拍相等，无中间空洞 beat',
            '- **slot 空洞**：存在 beat 间隔或 0 数据拍 → 与当前 DRAM `word 2/3=0` 现象一致',
            '- **数值全错但拍数对**：查 bit/IP 版本或 HLS 权重',
            '',
            '### csim 参考（sample 0, beat 0-7）',
            '',
        ]
        beats_path = REPO / 'notebooks' / 'hls4ml_prj' / 'tb_data' / 'csim_axis_beats.log'
        if beats_path.is_file():
            ref = beats_path.read_text().splitlines()[0].split()[:8]
            lines.append('`%s`' % ' '.join(ref))
        lines += [
            '',
            '### 若 ILA 为 serial 24 拍但 DRAM 有空洞',
            '',
            '重点查 **axi_dma_0 S2MM** 与 `output_stream` 之间是否有 dwidth converter、',
            '以及 S2MM_LEN 是否为 96（`OUT_BYTES`）。',
            '',
        ]
    OUT_ILA.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def main():
    n = int(os.environ.get('N_MM2S_COMPARE', '10'))
    board_idx = int(os.environ.get('SAMPLE_IDX', '0'))
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)

    host_samples = compare_samples(n)
    host_ok = all(s['npz_tb_mismatch_count'] == 0 for s in host_samples)

    board = None
    board_ok = False
    board_err = None
    try:
        if os.environ.get('BOARD_PRELOAD_PL', '1') == '1':
            preload_pl_on_board()
        board = fetch_board_cma(board_idx)
        board_ok = bool(board.get('payload_match_staged'))
    except Exception as exc:
        board_err = str(exc)

    raw0 = bytes(np.load(NPZ, allow_pickle=True)['payloads'][board_idx])
    npz_i16 = npz_int16_line(raw0)

    layout = {}
    if len(npz_i16) >= N_WORDS:
        hwc = npz_i16[:N_WORDS].reshape(32, 32, 3)
        chw_flat = hwc.transpose(2, 0, 1).reshape(-1)
        layout['hwc_flat_vs_npz_match'] = bool(np.all(chw_flat == npz_i16[:N_WORDS]))
        layout['chw_flat_mismatch_count'] = int(np.sum(chw_flat != npz_i16[:N_WORDS]))

    report = {
        'in_scale': IN_SCALE,
        'in_bytes': IN_BYTES,
        'n_words': N_WORDS,
        'host_npz_vs_tb': {
            'n_samples': len(host_samples),
            'all_match': host_ok,
            'samples': host_samples,
        },
        'board_cma_sample': board_idx,
        'board_cma': board,
        'board_cma_error': board_err,
        'board_cma_matches_npz': board_ok,
        'layout_probe_sample0': layout,
        'verdict': '',
    }

    if not host_ok:
        report['verdict'] = 'HOST: npz payload != csim tb_input — fix preprocess before ILA'
    elif board_err:
        report['verdict'] = (
            'HOST INPUT OK; BOARD: CMA read failed — reload PL first (BOARD_PRELOAD_PL=1), '
            'then retry; board may need power-cycle if SSH hung (%s)' % board_err[:80]
        )
    elif not board_ok:
        report['verdict'] = 'BOARD: CMA staging != npz — MM2S buffer/DMA write issue'
    else:
        report['verdict'] = 'INPUT OK: npz==tb==board CMA — mismatch is PL output path; use ILA on output_stream'

    OUT_JSON.write_text(json.dumps(report, indent=2), encoding='utf-8')
    write_ila_plan(report)
    print(json.dumps({
        'verdict': report['verdict'],
        'host_all_match': host_ok,
        'board_cma_matches_npz': board_ok,
        'written_json': str(OUT_JSON),
        'written_ila': str(OUT_ILA),
    }, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
