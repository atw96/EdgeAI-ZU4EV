#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
H=${EDGEAI_ROOT}
ps -ef | grep -E 'p1_narrow_1k|csim.exe|vivado_hls' | grep -v grep | awk '{print $2,$3,$8,$9,$10,$11}' || echo none
echo ----TAIL----
tail -n 8 "$H/results/opt_v2/logs/p1_narrow_1k.log" 2>/dev/null || echo no_log
echo ----LINES----
wc -l "$H/notebooks/hls4ml_prj/tb_data/csim_results.log" \
  "$H/notebooks/hls4ml_prj.bak_bitexact_p1_narrow_p4/tb_data/csim_results.log" \
  "$H/results/opt_v2/p1_narrow_p4_csim.log" \
  "$H/results/opt_v2/p1_narrow_a1_csim.log" 2>/dev/null || true
echo ----GATE----
cat "$H/results/opt_v2/p1_narrow_gate.json" 2>/dev/null || echo no_gate
