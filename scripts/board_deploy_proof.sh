#!/bin/sh
# Run ON THE BOARD (serial COM or SSH) to print deployment proof logs.
# Usage on board:
#   sh board_deploy_proof.sh
# Or from WSL/host:
#   sshpass -p root ssh root@192.168.1.40 'sh -s' < scripts/board_deploy_proof.sh
set -e

echo "============================================================"
echo " EdgeAI-ZU4EV — Board Deployment Proof"
echo "============================================================"
echo "Time     : $(date -Iseconds 2>/dev/null || date)"
echo "Hostname : $(hostname 2>/dev/null || echo unknown)"
echo "Kernel   : $(uname -r 2>/dev/null || echo unknown)"
echo ""

BIT=/lib/firmware/cifar10_accel.bit
echo "--- 1. Bitstream ---"
if [ -f "$BIT" ]; then
    ls -la "$BIT"
    md5sum "$BIT" 2>/dev/null || true
else
    echo "MISSING: $BIT"
    exit 1
fi
echo ""

echo "--- 2. FPGA Manager ---"
cat /sys/class/fpga_manager/fpga0/state 2>/dev/null || echo "fpga state: unknown"
dmesg 2>/dev/null | grep -i fpga | tail -3 || true
echo ""

echo "--- 3. DMA register peek (AXI DMA @ 0x80040000) ---"
python3 - <<'PY' 2>/dev/null || echo "python3 /dev/mem peek skipped"
import mmap, os, struct
fd = os.open('/dev/mem', os.O_RDWR | os.O_SYNC)
mm = mmap.mmap(fd, 0x1000, mmap.MAP_SHARED, mmap.PROT_READ|mmap.PROT_WRITE, offset=0x80040000)
mm2s = struct.unpack('<I', mm[0x04:0x08])[0]
s2mm = struct.unpack('<I', mm[0x34:0x38])[0]
mm.close(); os.close(fd)
print("MM2S_SR=0x%08X  S2MM_SR=0x%08X" % (mm2s, s2mm))
PY
echo ""

echo "--- 4. Inference demo (board_infer.py) ---"
if [ -f /tmp/board_infer.py ]; then
    python3 -u /tmp/board_infer.py 2>&1 | head -40
elif [ -f ./board_infer.py ]; then
    python3 -u ./board_infer.py 2>&1 | head -40
else
    echo "Upload scripts/board_infer.py to /tmp/ first, e.g.:"
    echo "  scp scripts/board_infer.py root@<board>:/tmp/"
fi
echo ""

echo "--- 5. Benchmark summary (if present) ---"
for f in /tmp/edgeai_bench/fpga_benchmark.json ./fpga_benchmark.json; do
    if [ -f "$f" ]; then
        echo "File: $f"
        cat "$f"
        break
    fi
done
echo ""
echo "=== Proof log complete ==="
