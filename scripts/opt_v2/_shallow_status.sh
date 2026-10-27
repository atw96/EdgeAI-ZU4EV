#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
H=${EDGEAI_ROOT}
echo ----JSON----
cat "$H/results/opt_v2/a1_shallow_csynth.json" 2>/dev/null || echo no_json
echo ----TAIL----
tail -n 15 "$H/results/opt_v2/logs/a1_shallow_csynth.log" 2>/dev/null || true
echo ----PROCS----
ps -ef | grep -E 'a1_shallow|p5_|vivado_hls' | grep -v grep | awk '{print $2,$8,$9,$10}' || echo none
