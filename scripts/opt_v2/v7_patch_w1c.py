from pathlib import Path
p = str(Path(__file__).resolve().parents[2] / 'scripts/opt_v2/v7_w1b.py')
s = open(p).read()
old = '''def wait_ioc(dma, poll_s):
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
'''
new = '''def ensure_idle(dma):
    """Reset if needed, then require both IOC bits to read 0 before a new transfer."""
    for _ in range(3):
        dma.clear_ioc()
        s2mm = dma.rd(DMA + S2MM_SR)
        mm2s = dma.rd(DMA + MM2S_SR)
        if not (s2mm & IOC) and not (mm2s & IOC) and not (s2mm & ERR_MASK) and not (mm2s & ERR_MASK):
            return True
        if not dma.soft_reset():
            print("RESET_FAIL", "s2mm", "0x%08x" % s2mm, flush=True)
            return False
        dma.clear_ioc()
    s2mm = dma.rd(DMA + S2MM_SR)
    mm2s = dma.rd(DMA + MM2S_SR)
    print("IOC_STUCK", "s2mm", "0x%08x" % s2mm, "mm2s", "0x%08x" % mm2s, flush=True)
    return False


def wait_ioc(dma, poll_s):
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
'''
if old not in s:
    raise SystemExit("wait block missing")
s = s.replace(old, new, 1)
old = '''        if do_reset:
            if not dma.soft_reset():
                print("RESET_FAIL", seen, flush=True)
                return None
        dma.clear_ioc()
        marks.append(time.perf_counter())
'''
new = '''        if do_reset:
            if not dma.soft_reset():
                print("RESET_FAIL", seen, flush=True)
                return None
        if not ensure_idle(dma):
            return None
        marks.append(time.perf_counter())
'''
if old not in s:
    raise SystemExit("clear block missing")
s = s.replace(old, new, 1)
open(p, "w").write(s)
print("patched")
