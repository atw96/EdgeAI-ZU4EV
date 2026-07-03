"""DMA S2MM slot packing: pair int16 into writable 32-bit word indices."""
import os
import struct


def slot32_out_bytes(n_outputs):
    """Bytes for slot-packed AXIS stream (includes hole beats + TLAST pad)."""
    n_pairs = (n_outputs + 1) // 2
    if n_pairs == 0:
        return 4
    last_beat = (n_pairs - 1) + 2 * ((n_pairs - 1) // 2)
    return (last_beat + 2) * 4


def slot_beat_maps(n_outputs):
    """Return (beat_lo, beat_hi, n_beats) for HLS slot pack mode."""
    n_pairs = (n_outputs + 1) // 2
    if n_pairs == 0:
        return [-1], [-1], 1
    last_beat = (n_pairs - 1) + 2 * ((n_pairs - 1) // 2)
    n_beats = last_beat + 2
    beat_lo = [-1] * n_beats
    beat_hi = [-1] * n_beats
    for p in range(n_pairs):
        beat = p + 2 * (p // 2)
        lo = p * 2
        hi = lo + 1
        beat_lo[beat] = lo
        beat_hi[beat] = hi if hi < n_outputs else -1
    return beat_lo, beat_hi, n_beats


def slot32_word_map(n_outputs):
    """DRAM word index -> tuple of logit indices stored in that 32-bit word."""
    n_pairs = (n_outputs + 1) // 2
    mapping = {}
    for p in range(n_pairs):
        beat = p + 2 * (p // 2)
        lo = p * 2
        hi = lo + 1
        if hi < n_outputs:
            mapping[beat] = (lo, hi)
        else:
            mapping[beat] = (lo,)
    return mapping


def serial32_out_bytes(n_outputs):
    """Bytes for serial 32-bit AXIS (one logit per beat, low 16 bits)."""
    return int(n_outputs) * 4


def decode_serial32_raw(raw, out_scale, n_outputs=None):
    if n_outputs is None:
        n_outputs = int(os.environ.get('OUT_DIM', '10'))
    scale = float(out_scale)
    scores = []
    for idx in range(n_outputs):
        lo_v = struct.unpack_from('<h', raw, idx * 4)[0]
        scores.append(lo_v / scale)
    return scores


def decode_slot32_raw(raw, out_scale, n_outputs=None):
    if n_outputs is None:
        n_outputs = int(os.environ.get('OUT_DIM', '10'))
    scores = [0.0] * n_outputs
    scale = float(out_scale)
    for word_idx, logits in slot32_word_map(n_outputs).items():
        if len(logits) == 2:
            lo_v, hi_v = struct.unpack_from('<hh', raw, word_idx * 4)
            scores[logits[0]] = lo_v / scale
            scores[logits[1]] = hi_v / scale
        else:
            lo_v = struct.unpack_from('<h', raw, word_idx * 4)[0]
            scores[logits[0]] = lo_v / scale
    return scores



def decode_board_s2mm_raw(raw, out_scale, n_outputs=None):
    """Board S2MM: slot hole beats in stream, one int16 per writable beat (low 16 bits)."""
    if n_outputs is None:
        n_outputs = int(os.environ.get('OUT_DIM', '10'))
    beat_lo, beat_hi, n_beats = slot_beat_maps(n_outputs)
    writable = [b for b in range(n_beats) if beat_lo[b] >= 0]
    scale = float(out_scale)
    scores = [0.0] * n_outputs
    li = 0
    for beat in writable:
        if li >= n_outputs:
            break
        v = struct.unpack_from('<h', raw, beat * 4)[0] / scale
        scores[li] = v
        li += 1
    return scores


def decode_board_paired_beats_raw(raw, out_scale, n_outputs=None):
    """Same stream layout; assign writable[i] to scores[i]."""
    if n_outputs is None:
        n_outputs = int(os.environ.get('OUT_DIM', '10'))
    beat_lo, beat_hi, n_beats = slot_beat_maps(n_outputs)
    writable = [b for b in range(n_beats) if beat_lo[b] >= 0]
    scale = float(out_scale)
    scores = [0.0] * n_outputs
    for i in range(0, min(len(writable), n_outputs)):
        beat = writable[i]
        scores[i] = struct.unpack_from('<h', raw, beat * 4)[0] / scale
    return scores


def decode_board_s2mm_beatlo_raw(raw, out_scale, n_outputs=None):
    """Board S2MM: map each writable beat to scores[beat_lo[beat]]."""
    if n_outputs is None:
        n_outputs = int(os.environ.get('OUT_DIM', '10'))
    beat_lo, beat_hi, n_beats = slot_beat_maps(n_outputs)
    scale = float(out_scale)
    scores = [0.0] * n_outputs
    for beat in range(n_beats):
        if beat_lo[beat] < 0:
            continue
        idx = beat_lo[beat]
        if idx < n_outputs:
            scores[idx] = struct.unpack_from('<h', raw, beat * 4)[0] / scale
    return scores

def fmt_c_int_array(vals):
    return '{' + ', '.join(str(v) for v in vals) + '}'
