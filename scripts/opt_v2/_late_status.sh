#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
H=${EDGEAI_ROOT}
echo ----P5----
cat "$H/results/opt_v2/p5_indexloop.json" 2>/dev/null || echo no_p5
echo ----PROCS----
ps -ef | grep -E 'p5_indexloop|a1_shallow_csim|a1_shallow_syn|csim.exe|vivado_hls' | grep -v grep | awk '{print $2,$8,$9,$10}' || echo none
echo ----CSIMTAIL----
tail -n 5 "$H/results/opt_v2/logs/a1_shallow_csim.log" 2>/dev/null || echo no_csim_log
echo ----SYNTAIL----
tail -n 4 "$H/results/opt_v2/logs/a1_shallow_syn_outer.log" 2>/dev/null || true
