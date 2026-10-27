#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
H=${EDGEAI_ROOT}
echo ----PROCS----
ps -ef | grep -E 'p2b_narrow|a1_after|a1_narrow|p4_after|vivado_hls' | grep -v grep | awk '{print $2,$8,$9,$10}' || echo none
echo ----P2BJSON----
cat "$H/results/opt_v2/p2b_narrow_p4.json" 2>/dev/null || echo no_p2b_json
echo ----P2BTAIL----
tail -n 12 "$H/results/opt_v2/logs/p2b_narrow_p4.log" 2>/dev/null || true
echo ----A1OUTER----
tail -n 8 "$H/results/opt_v2/logs/a1_after_p2b_outer.log" 2>/dev/null || true
echo ----A1LOG----
tail -n 6 "$H/results/opt_v2/logs/a1_narrow_csynth.log" 2>/dev/null || true
