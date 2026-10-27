#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
H=${EDGEAI_ROOT}
echo "=== stdout ==="
wc -c "$H/results/opt_v2/logs/v9_csim729.log.stdout" 2>&1
tail -n 40 "$H/results/opt_v2/logs/v9_csim729.log.stdout" 2>&1
echo "=== ldd ==="
ldd "$H/notebooks/hls4ml_prj_a2l/myproject_prj/solution1/csim/build/csim.exe" 2>&1 | head
echo "=== work ==="
ls -la /tmp/v9_csim729 /tmp/v9_csim729/tb_data 2>&1 | head
