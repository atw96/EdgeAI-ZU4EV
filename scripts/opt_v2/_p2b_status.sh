#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
H=${EDGEAI_ROOT}
ps -ef | grep -E 'p2b_narrow|vivado_hls' | grep -v grep | awk '{print $2,$8,$9,$10,$11,$12}' || echo none
echo ----
tail -n 15 "$H/results/opt_v2/logs/p2b_narrow_p4.log" 2>/dev/null || echo no_log
