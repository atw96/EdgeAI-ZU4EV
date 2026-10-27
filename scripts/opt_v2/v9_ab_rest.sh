#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
# Finish the two A/B cells the 50 ms deadline could not measure.
# Old bitstream latency is about 57 ms, so this binary waits up to 500 ms.
set -uo pipefail
export SSHPASS="${SSHPASS:?SSHPASS}"
OPTS="-o ConnectTimeout=8 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ServerAliveInterval=15 -o ServerAliveCountMax=280"
IP=${BOARD_IP:?BOARD_IP}
H=${EDGEAI_ROOT}
M=${EDGEAI_ROOT}
GCC=/tools/Xilinx/Vitis/2020.1/gnu/aarch64/lin/aarch64-linux/bin/aarch64-linux-gnu-gcc
LOG=$H/results/opt_v2/logs/v9_ab_rest.log
mkdir -p "$H/results/opt_v2/logs"
exec > >(tee -a "$LOG") 2>&1
echo "[$(date '+%F %T')] v9 ab rest"
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
needle = "static int wait_ioc(uint32_t *s2_out)\n{\n    double deadline = now_ms() + 50.0;"
repl = "static int wait_ioc(uint32_t *s2_out)\n{\n    double deadline = now_ms() + 500.0;"
if needle not in src:
    raise SystemExit("deadline site missing")
src = src.replace(needle, repl, 1)
open("/tmp/v9_x2_count.c", "w").write(src)
print("patched")
PY
"$GCC" -O2 -std=c11 -Wall -o /tmp/v9_x2_count /tmp/v9_x2_count.c
sed -i 's/\r$//' "$M/scripts/opt_v2/v9_ab_rest_remote.sh"
timeout 40 sshpass -e scp $OPTS /tmp/v9_x2_count "$M/scripts/opt_v2/v9_ab_rest_remote.sh" root@$IP:/tmp/edgeai_bench/
timeout 4000 sshpass -e ssh $OPTS root@$IP 'sh /tmp/edgeai_bench/v9_ab_rest_remote.sh'
echo AB_REST_HOST_RC $?
