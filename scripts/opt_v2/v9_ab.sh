#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
# R2 FPGA cells. One SSH. Restores RC2 at DIVISOR0=10 on exit.
set -uo pipefail
export SSHPASS="${SSHPASS:?SSHPASS}"
OPTS="-o ConnectTimeout=8 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ServerAliveInterval=15 -o ServerAliveCountMax=280"
IP=${BOARD_IP:?BOARD_IP}
H=${EDGEAI_ROOT}
M=${EDGEAI_ROOT}
GCC=/tools/Xilinx/Vitis/2020.1/gnu/aarch64/lin/aarch64-linux/bin/aarch64-linux-gnu-gcc
LOG=$H/results/opt_v2/logs/v9_ab.log
mkdir -p "$H/results/opt_v2/logs"
exec > >(tee -a "$LOG") 2>&1
echo "[$(date '+%F %T')] v9 ab"
python3 - << 'PY'
src = open(__import__("os").environ["EDGEAI_ROOT"] + '/scripts/opt_v2/v8_x2_hot.c').read()
old = """        if (aa >= 0 || err || pred != top1[idx]) {
            events++;
            fprintf(stderr, "MISMATCH frame %d lsb %d aa %d pred %d gold %d\\n",
                    i, err, aa, pred, top1[idx]);
            return 5;
        }"""
new = """        if (aa >= 0 || err || pred != top1[idx]) {
            events++;
            if (events <= 3)
                fprintf(stderr, "MISMATCH frame %d lsb %d aa %d pred %d gold %d\\n",
                        i, err, aa, pred, top1[idx]);
        }"""
if old not in src:
    raise SystemExit("patch site missing")
src = src.replace(old, new, 1)
src = src.replace("if (seen % 20000 == 0)", "if (seen % 2000 == 0)", 1)
open("/tmp/v9_x2_count.c", "w").write(src)
print("patched")
PY
"$GCC" -O2 -std=c11 -Wall -o /tmp/v9_x2_count /tmp/v9_x2_count.c
file /tmp/v9_x2_count
sed -i 's/\r$//' "$M/scripts/opt_v2/v9_ab_remote.sh"
timeout 40 sshpass -e scp $OPTS /tmp/v9_x2_count "$M/scripts/opt_v2/v9_ab_remote.sh" root@$IP:/tmp/edgeai_bench/
timeout 4200 sshpass -e ssh $OPTS root@$IP 'sh /tmp/edgeai_bench/v9_ab_remote.sh'
echo AB_HOST_RC $?
