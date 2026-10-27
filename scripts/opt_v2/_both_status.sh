#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
H=${EDGEAI_ROOT}
echo ----P4----
tail -n 30 "$H/results/opt_v2/logs/p4_micro_convert.log" 2>/dev/null || echo no_p4
echo ----P2B----
tail -n 6 "$H/results/opt_v2/logs/p2b_narrow_p4.log" 2>/dev/null || echo no_p2b
ps -ef | grep -E 'p4_micro_convert|p2b_narrow' | grep -v grep | awk '{print $2,$8,$9}' || echo none
