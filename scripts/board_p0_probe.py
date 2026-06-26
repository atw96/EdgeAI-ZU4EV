#!/usr/bin/env python3
"""P0 board probes: S2MM_LEN, clean DST, input variation, queue, bit md5."""
import hashlib
import json
import os
import struct
import subprocess
import sys
import time

import numpy as np

from dma_infer_common import (
    DevMemDma, DMA, DST_PHYS, SRC_PHYS, IN_BYTES, OUT_BYTES,
    MM2S_CR, MM2S_SR, MM2S_SA, MM2S_SA_MSB, MM2S_LEN,
    S2MM_CR, S2MM_SR, S2MM_DA, S2MM_DA_MSB, S2MM_LEN, IOC,
)

DST_CLEAN = int(os.environ.get('DST_CLEAN_PHYS', '0x66C02100'), 0)
CLEAN_BYTES = int(os.environ.get('CLEAN_SCAN_BYTES', '64'))
BIT_PATH = os.environ.get('BOARD_BIT_PATH', '/lib/firmware/cifar10_accel.bit')


def load_payloads(n=3):
    npz = os.environ.get('BENCH_NPZ', 'cifar10_bench.npz')
    if not os.path.isabs(npz):
        npz = os.path.join(os.path.dirname(os.path.abspath(__file__)), npz)
    data = np.load(npz, allow_pickle=True)
    payloads = [bytes(data['payloads'][i]) for i in range(min(n, len(data['payloads'])))]
    labels = [int(data['labels'][i]) for i in range(len(payloads))]
    return payloads, labels


def int16_head(raw, n=4):
    return [struct.unpack_from('<h', raw, k * 2)[0] for k in range(n)]


def run_full_transfer(dma, dst_phys=DST_PHYS, out_len=OUT_BYTES, payload=None):
    if payload is None:
        payload = b'\x00' * IN_BYTES
    dma.soft_reset()
    dma.clear_ioc()
    dma.flush_write(SRC_PHYS, payload)
    dma.wr(DMA + S2MM_DA, dst_phys)
    dma.wr(DMA + S2MM_DA_MSB, 0)
    dma.wr(DMA + S2MM_CR, dma.rd(DMA + S2MM_CR) | 0x1)
    dma.wr(DMA + S2MM_LEN, out_len)
    dma.wr(DMA + MM2S_SA, SRC_PHYS)
    dma.wr(DMA + MM2S_SA_MSB, 0)
    dma.wr(DMA + MM2S_CR, dma.rd(DMA + MM2S_CR) | 0x1)
    dma.wr(DMA + MM2S_LEN, IN_BYTES)
    ok, mm2s, s2mm, st = dma.wait_ioc()
    s2mm_len = dma.rd(DMA + S2MM_LEN)
    return {
        'ok': ok, 'status': st, 'mm2s_sr': mm2s, 's2mm_sr': s2mm,
        's2mm_len_reg': s2mm_len,
    }


def probe_s2mm_len(dma, payload):
    print('\n=== P0-1 S2MM_LEN readback ===')
    r = run_full_transfer(dma, payload=payload)
    raw = dma.inv_read(DST_PHYS, OUT_BYTES, after_dma=True)
    r['raw20_hex'] = raw[:20].hex()
    r['int16_0_3'] = int16_head(raw, 4)
    r['int16_4_7'] = [
        struct.unpack_from('<h', raw, k * 2)[0] for k in range(4, 8)
    ]
    if r['s2mm_len_reg'] == 8:
        r['mechanism_hint'] = 'B_early_tlast_8_bytes'
    elif r['s2mm_len_reg'] == 20:
        r['mechanism_hint'] = 'A_full_20_bytes_check_wstrb'
    else:
        r['mechanism_hint'] = 'unexpected_len_%d' % r['s2mm_len_reg']
    print(json.dumps(r, indent=2))
    return r


def probe_clean_dst(dma, payload):
    print('\n=== P0-2 clean DST @ 0x%x ===' % DST_CLEAN)
    dma.soft_reset()
    dma.clear_ioc()
    dma.flush_write(SRC_PHYS, payload)
    dma.flush_write(DST_CLEAN, b'\xaa' * CLEAN_BYTES)
    dma.wr(DMA + S2MM_DA, DST_CLEAN)
    dma.wr(DMA + S2MM_DA_MSB, 0)
    dma.wr(DMA + S2MM_CR, dma.rd(DMA + S2MM_CR) | 0x1)
    dma.wr(DMA + S2MM_LEN, OUT_BYTES)
    dma.wr(DMA + MM2S_SA, SRC_PHYS)
    dma.wr(DMA + MM2S_SA_MSB, 0)
    dma.wr(DMA + MM2S_CR, dma.rd(DMA + MM2S_CR) | 0x1)
    dma.wr(DMA + MM2S_LEN, IN_BYTES)
    ok, mm2s, s2mm, st = dma.wait_ioc()
    s2mm_len = dma.rd(DMA + S2MM_LEN)
    raw = dma.inv_read(DST_CLEAN, CLEAN_BYTES, after_dma=True)
    written = [i for i in range(min(32, CLEAN_BYTES)) if raw[i] != 0xAA]
    r = {
        'ok': ok, 'status': st, 's2mm_len_reg': s2mm_len,
        'hex64': raw[:64].hex(),
        'non_aa_offsets': written,
        'bytes_8_15': list(raw[8:16]),
        'bytes_16_19': list(raw[16:20]),
    }
    if all(raw[i] == 0xAA for i in range(8, 16)):
        r['mid_verdict'] = 'beat_not_written'
    elif all(raw[i] == 0 for i in range(8, 16)):
        r['mid_verdict'] = 'pl_wrote_zero'
    else:
        r['mid_verdict'] = 'mixed_or_partial'
    print(json.dumps(r, indent=2))
    return r


def probe_input_variation(dma, payloads, labels):
    print('\n=== P0-3 input variation (3 samples) ===')
    heads = []
    for i, payload in enumerate(payloads):
        r = run_full_transfer(dma, payload=payload)
        raw = dma.inv_read(DST_PHYS, OUT_BYTES, after_dma=True)
        h = int16_head(raw, 4)
        heads.append({'sample': i, 'label': labels[i], 'int16_0_3': h, 'raw8_hex': raw[:8].hex()})
        print('  sample%d label=%s int16[0:3]=%s raw8=%s' % (i, labels[i], h, raw[:8].hex()))
    same = all(heads[0]['int16_0_3'] == h['int16_0_3'] for h in heads[1:])
    r = {'heads': heads, 'logits_0_3_identical': same}
    if same:
        r['hint'] = 'input_path_or_core_constant — pause output-side fixes'
    else:
        r['hint'] = 'output_varies_with_input — output path issue likely'
    print(json.dumps(r, indent=2))
    return r


def probe_s2mm_only_queue(dma, payload):
    print('\n=== P0-4 S2MM-only queue probe ===')
    run_full_transfer(dma, payload=payload)
    dma.clear_ioc()
    dma.wr(DMA + S2MM_DA, DST_PHYS)
    dma.wr(DMA + S2MM_DA_MSB, 0)
    dma.wr(DMA + S2MM_CR, dma.rd(DMA + S2MM_CR) | 0x1)
    dma.wr(DMA + S2MM_LEN, OUT_BYTES)
    t0 = time.perf_counter()
    deadline = t0 + 3.0
    got_ioc = False
    while time.perf_counter() < deadline:
        s2mm = dma.rd(DMA + S2MM_SR)
        if s2mm & 0x770:
            break
        if s2mm & IOC:
            got_ioc = True
            break
        time.sleep(0.002)
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    s2mm_len = dma.rd(DMA + S2MM_LEN)
    r = {
        's2mm_only_ioc': got_ioc,
        'elapsed_ms': round(elapsed_ms, 2),
        's2mm_sr': dma.rd(DMA + S2MM_SR),
        's2mm_len_reg': s2mm_len,
    }
    if got_ioc:
        r['hint'] = 'queued_output_packet — early TLAST / multi-beat backlog likely'
    else:
        r['hint'] = 'no_queued_packet_on_s2mm_only'
    print(json.dumps(r, indent=2))
    return r


def probe_bit_loaded():
    print('\n=== P0-5 bit load verification ===')
    r = {'bit_path': BIT_PATH}
    if os.path.isfile(BIT_PATH):
        with open(BIT_PATH, 'rb') as f:
            r['board_bit_md5'] = hashlib.md5(f.read()).hexdigest()
        r['board_bit_size'] = os.path.getsize(BIT_PATH)
        r['board_bit_mtime'] = time.ctime(os.path.getmtime(BIT_PATH))
    else:
        r['board_bit_md5'] = None
        r['error'] = 'bit file missing on board'
    try:
        out = subprocess.check_output(['dmesg'], stderr=subprocess.DEVNULL, text=True)
        fpga_lines = [ln for ln in out.splitlines() if 'fpga' in ln.lower()][-8:]
        r['dmesg_fpga_tail'] = fpga_lines
    except Exception as exc:
        r['dmesg_error'] = str(exc)
    try:
        state = open('/sys/class/fpga_manager/fpga0/state').read().strip()
        r['fpga_manager_state'] = state
    except OSError as exc:
        r['fpga_manager_state'] = str(exc)
    print(json.dumps(r, indent=2))
    return r


def decide_p2(report):
    p2 = {'actions': [], 'conclusion': None}
    s2mm = report.get('p0_1_s2mm_len', {})
    clean = report.get('p0_2_clean_dst', {})
    inp = report.get('p0_3_input_variation', {})
    bit = report.get('p0_5_bit', {})

    wsl_md5 = report.get('wsl_bit_md5')
    board_md5 = bit.get('board_bit_md5')
    if wsl_md5 and board_md5 and wsl_md5 != board_md5:
        p2['conclusion'] = 'bit_deploy_mismatch'
        p2['actions'].append('Fix board_auto_fix.sh deploy/reload; re-run P0')
        return p2

    if inp.get('logits_0_3_identical'):
        p2['conclusion'] = 'input_path_broken'
        p2['actions'].append('Pause all output-side fixes; debug MM2S->axis_to_model_stream')
        return p2

    slen = s2mm.get('s2mm_len_reg')
    if slen == 8:
        p2['conclusion'] = 'mechanism_B_early_tlast'
        p2['actions'].append('Wait head-Latency pipeline OR fix HLS output beat count')
    elif slen == 20:
        p2['conclusion'] = 'mechanism_A_wstrb_or_stale_dram'
        p2['actions'].append('Run axis32_out pipeline OR ILA on TKEEP/TLAST')
        if clean.get('mid_verdict') == 'beat_not_written':
            p2['actions'].append('Clean DST confirms bytes 8-15 not written by PL')
    else:
        p2['conclusion'] = 'inconclusive_s2mm_len_%s' % slen
        p2['actions'].append('Run P1 RTL cosim for beat-level truth')

    queue = report.get('p0_4_queue', {})
    if queue.get('s2mm_only_ioc'):
        p2['actions'].append('Queue probe positive — investigate TLAST/packet boundaries')

    return p2


def main():
    payloads, labels = load_payloads(3)
    dma = DevMemDma()
    report = {'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S')}
    try:
        report['p0_1_s2mm_len'] = probe_s2mm_len(dma, payloads[0])
        report['p0_2_clean_dst'] = probe_clean_dst(dma, payloads[0])
        report['p0_3_input_variation'] = probe_input_variation(dma, payloads, labels)
        report['p0_4_queue'] = probe_s2mm_only_queue(dma, payloads[0])
    finally:
        dma.close()

    report['p0_5_bit'] = probe_bit_loaded()
    report['p2_decision'] = decide_p2(report)

    out_json = os.environ.get('P0_REPORT_JSON', 'p0_probe_report.json')
    with open(out_json, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2)
    print('\n=== P2 decision ===')
    print(json.dumps(report['p2_decision'], indent=2))
    print('Wrote %s' % out_json)
    return 0


if __name__ == '__main__':
    sys.exit(main())
