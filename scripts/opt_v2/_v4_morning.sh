#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
H=${EDGEAI_ROOT}
echo "==== procs ===="
ps -ef | grep -E 'v4_csim_10k|v4_after_csim|csim.exe|vivado_hls' | grep -v grep || echo none
echo "==== closer ===="
tail -n 40 "$H/results/opt_v2/logs/v4_after_csim.log" 2>/dev/null || echo no_closer
echo "==== csim log tail ===="
tail -n 15 "$H/results/opt_v2/logs/v4_csim_10k.log" 2>/dev/null || echo no_csim_log
echo "==== files ===="
ls -l "$H/results/opt_v2/v4_d3.json" "$H/results/opt_v2/v4_d3_csim10k.json" "$H/results/opt_v2/v4_csim_10k.log" "$H/results/opt_v2/v4_csim_extreme.log" "$H/results/opt_v2/v4_extreme_csim.txt" "$H/results/opt_v2/e2e_report.json" 2>&1 | head -n 30
echo "==== lines ===="
wc -l "$H/notebooks/hls4ml_prj/tb_data/csim_results.log" "$H/results/opt_v2/v4_csim_10k.log" 2>/dev/null || true
date
