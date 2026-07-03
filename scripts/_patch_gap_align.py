from pathlib import Path
p = Path("/home/atw/Edge_AI_Acc/claude/EdgeAI-ZU4EV_Claude/scripts/gap_axi_csim_board_align.py")
text = p.read_text(encoding="utf-8")
text = text.replace("OUT_BYTES = int(os.environ.get('OUT_BYTES', '92'))", "OUT_BYTES = int(os.environ.get('OUT_BYTES', '96'))")
if "OUTPUT_PACK_MODE" not in text:
    text = text.replace(
        "OUT_BYTES = int(os.environ.get('OUT_BYTES', '96'))\n",
        "OUT_BYTES = int(os.environ.get('OUT_BYTES', '96'))\nOUTPUT_PACK_MODE = os.environ.get('OUTPUT_PACK_MODE', 'slot').lower()\n",
    )
old = """    beat_lo, beat_hi, n_beats = slot_beat_maps(OUT_DIM)
    samples = []"""
new = """    pack_serial = OUTPUT_PACK_MODE == 'serial'
    if pack_serial:
        n_beats = OUT_DIM
    else:
        beat_lo, beat_hi, n_beats = slot_beat_maps(OUT_DIM)
    samples = []"""
if "pack_serial" not in text:
    text = text.replace(old, new)
old_loop = """        board_words = board_words_from_raw(raw)
        csim_words, _ = csim_words_from_beats(csim_beats[i])

        beat_cmp = []
        writable_beats = [b for b in range(n_beats) if beat_lo[b] >= 0]
        for beat in range(n_beats):
            bw = board_words[beat] if beat < len(board_words) else 0
            cw = csim_words.get(beat, 0)
            is_writable = beat_lo[beat] >= 0
            beat_cmp.append({
                'beat': beat,
                'writable': is_writable,
                'board_word': bw,
                'csim_word': cw,
                'match': (bw == cw) if is_writable else None,
                'lo_idx': beat_lo[beat],
                'hi_idx': beat_hi[beat],
            })

        slot_cmp = []
        for word_idx, logits in slot32_word_map(OUT_DIM).items():
            bw = board_words[word_idx] if word_idx < len(board_words) else 0
            cw = csim_words.get(word_idx, 0)
            slot_cmp.append({
                'word_idx': word_idx,
                'logits': list(logits),
                'board_word': bw,
                'csim_word': cw,
                'match': bw == cw,
            })"""
new_loop = """        board_words = board_words_from_raw(raw)
        if pack_serial:
            beat_cmp = []
            slot_cmp = []
            csim_beat_list = csim_beats[i]
            for beat in range(n_beats):
                bw = board_words[beat] if beat < len(board_words) else 0
                cw = csim_beat_list[beat] if beat < len(csim_beat_list) else 0
                beat_cmp.append({
                    'beat': beat,
                    'writable': True,
                    'board_word': bw,
                    'csim_word': cw,
                    'match': bw == cw,
                    'lo_idx': beat,
                    'hi_idx': -1,
                })
        else:
            csim_words, _ = csim_words_from_beats(csim_beats[i])
            beat_cmp = []
            for beat in range(n_beats):
                bw = board_words[beat] if beat < len(board_words) else 0
                cw = csim_words.get(beat, 0)
                is_writable = beat_lo[beat] >= 0
                beat_cmp.append({
                    'beat': beat,
                    'writable': is_writable,
                    'board_word': bw,
                    'csim_word': cw,
                    'match': (bw == cw) if is_writable else None,
                    'lo_idx': beat_lo[beat],
                    'hi_idx': beat_hi[beat],
                })

            slot_cmp = []
            for word_idx, logits in slot32_word_map(OUT_DIM).items():
                bw = board_words[word_idx] if word_idx < len(board_words) else 0
                cw = csim_words.get(word_idx, 0)
                slot_cmp.append({
                    'word_idx': word_idx,
                    'logits': list(logits),
                    'board_word': bw,
                    'csim_word': cw,
                    'match': bw == cw,
                })"""
if "if pack_serial:" not in text:
    text = text.replace(old_loop, new_loop)
text = text.replace(
    "        bm = float(np.mean([r['match'] for r in beat_cmp if r['writable']]) * 100)\n        wm = float(np.mean([r['match'] for r in slot_cmp]) * 100)",
    "        bm = float(np.mean([r['match'] for r in beat_cmp if r.get('writable')]) * 100)\n        wm = float(np.mean([r['match'] for r in (slot_cmp if slot_cmp else beat_cmp)]) * 100)",
)
text = text.replace(
    "    if report['summary']['writable_slot_match_mean_pct'] > 80:",
    "    match_key = report['summary']['beat_word_match_mean_pct'] if pack_serial else report['summary']['writable_slot_match_mean_pct']\n    if match_key > 80:",
)
p.write_text(text, encoding="utf-8")
print("gap_axi_csim_board_align patched")