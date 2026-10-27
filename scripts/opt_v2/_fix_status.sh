#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
H=${EDGEAI_ROOT}
ps -ef | grep -E 'p1_fix_continue|csim.exe' | grep -v grep || echo none
echo ----
tail -n 20 "$H/results/opt_v2/logs/p1_fix_continue.log" 2>/dev/null || echo no_log
echo ----SMOKE----
cat "$H/results/opt_v2/p1_narrow_p4_n100.json" 2>/dev/null || echo no_smoke_json
