from pathlib import Path
src = str(Path(__file__).resolve().parents[2] / 'scripts/opt_v2/v7_w1.py')
dst = str(Path(__file__).resolve().parents[2] / 'scripts/opt_v2/v7_w1b.py')
s = open(src).read()
s = s.replace(
    'OUT_JSON = "/tmp/edgeai_bench/v7_w1.json"',
    'OUT_JSON = os.environ.get("W1_JSON", "/tmp/edgeai_bench/v7_w1b.json")',
)
s = s.replace(
    'EVENTS = "/tmp/edgeai_bench/v7_events.jsonl"',
    'EVENTS = os.environ.get("W1_EVENTS", "/tmp/edgeai_bench/v7_events_b.jsonl")',
)
old = """def wait_ioc(dma, poll_s):
    timeout_s = float(os.environ.get("DMA_IOC_TIMEOUT_S", "8"))
    deadline = time.perf_counter() + timeout_s
    polls = 0
    while time.perf_counter() < deadline:
        if poll_s:
            time.sleep(poll_s)
        polls += 1
        s2mm = dma.rd(DMA + S2MM_SR)
        mm2s = dma.rd(DMA + MM2S_SR)
        if (s2mm & ERR_MASK) or (mm2s & ERR_MASK):
            return False, mm2s, s2mm, "ERR", polls
        if (s2mm & IOC) and (mm2s & IOC):
            return True, mm2s, s2mm, "IOC", polls
    return False, dma.rd(DMA + MM2S_SR), dma.rd(DMA + S2MM_SR), "TIMEOUT", polls
"""
new = """def wait_ioc(dma, poll_s):
    timeout_s = float(os.environ.get("DMA_IOC_TIMEOUT_S", "8"))
    deadline = time.perf_counter() + timeout_s
    polls = 0
    seen_low_s2 = False
    seen_low_mm = False
    while time.perf_counter() < deadline:
        if poll_s:
            time.sleep(poll_s)
        polls += 1
        s2mm = dma.rd(DMA + S2MM_SR)
        mm2s = dma.rd(DMA + MM2S_SR)
        if (s2mm & ERR_MASK) or (mm2s & ERR_MASK):
            return False, mm2s, s2mm, "ERR", polls
        if not (s2mm & IOC):
            seen_low_s2 = True
        if not (mm2s & IOC):
            seen_low_mm = True
        if seen_low_s2 and seen_low_mm and (s2mm & IOC) and (mm2s & IOC):
            return True, mm2s, s2mm, "IOC", polls
    return False, dma.rd(DMA + MM2S_SR), dma.rd(DMA + S2MM_SR), "TIMEOUT", polls
"""
if old not in s:
    raise SystemExit("wait_ioc block missing")
s = s.replace(old, new, 1)
old = """    if do_reset and not dma.soft_reset():
        print("RESET_FAIL", flush=True)
        return None
    dma.clear_ioc()
"""
new = """    if not dma.soft_reset():
        print("RESET_FAIL", flush=True)
        return None
    dma.clear_ioc()
"""
if old not in s:
    raise SystemExit("initial reset block missing")
s = s.replace(old, new, 1)
old = """        if do_reset:
            if not dma.soft_reset():
                print("RESET_FAIL", seen, flush=True)
                return None
            dma.clear_ioc()
        marks.append(time.perf_counter())
"""
new = """        if do_reset:
            if not dma.soft_reset():
                print("RESET_FAIL", seen, flush=True)
                return None
        dma.clear_ioc()
        marks.append(time.perf_counter())
"""
if old not in s:
    raise SystemExit("per-frame reset block missing")
s = s.replace(old, new, 1)
old = """        if len(events) >= 5 and events[0].get("reread_inv_aa_bytes") == [] and events[0].get("first_aa_bytes"):
            print("SYSTEMATIC", mode, "events", len(events), "frames", seen, flush=True)
            break
"""
if old not in s:
    raise SystemExit("break block missing")
s = s.replace(old, "", 1)
open(dst, "w").write(s)
print("wrote", dst, len(s))
