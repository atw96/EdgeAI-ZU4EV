#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
H=${EDGEAI_ROOT}
echo "---- closer ----"
tail -n 8 "$H/results/opt_v2/logs/v4_after_csim.log" 2>/dev/null || echo no_closer_log
pgrep -af 'v4_after_csim|v4_csim_10k|csim.exe' | grep -v pgrep || echo none
echo "---- csim lines ----"
wc -l "$H/notebooks/hls4ml_prj/tb_data/csim_results.log"
date
