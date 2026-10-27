#!/bin/bash
# Reload RC1 and compare one KAT frame. Does not write the PL clock.
set -euo pipefail
export SSHPASS="${SSHPASS:?SSHPASS}"
OPTS="-o ConnectTimeout=8 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
IP=${BOARD_IP:?BOARD_IP}
timeout 40 sshpass -e ssh $OPTS root@$IP 'cd /tmp/edgeai_bench && FORCE_PL_RELOAD=1 sh board_load_only.sh && python3 board_fix_hp0_width.py && echo REG && python3 -c "import mmap,os,struct; fd=os.open(\"/dev/mem\", os.O_RDONLY|os.O_SYNC); mm=mmap.mmap(fd, 4096, mmap.MAP_SHARED, mmap.PROT_READ, offset=0xFF5E0000); print(hex(struct.unpack_from(\"<I\", mm, 0xC0)[0])); mm.close()"'
timeout 40 sshpass -e ssh $OPTS root@$IP 'cd /tmp/edgeai_bench && export OUT_DIM=24 OUT_BYTES=96 OUT_LAYOUT=gap_ps OUT_FIXED_SCALE=1024 OUTPUT_PACK_MODE=serial DMA_IOC_TIMEOUT_S=8 PYTHONUNBUFFERED=1 KAT_NPZ=/tmp/edgeai_bench/kat_packed.npz KAT_GOLDEN=/tmp/edgeai_bench/kat_golden.npz && python3 v6_kat_debug2.py'
