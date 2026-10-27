#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
H=${EDGEAI_ROOT}
echo "==== head ===="
head -n 20 "$H/results/opt_v2/logs/v4_resume_csim.log"
echo "==== ps ===="
ps -ef | grep -E 'csim.exe|v4_resume' | grep -v grep || echo none
echo "==== result lines now ===="
wc -l "$H/notebooks/hls4ml_prj/tb_data/csim_results.log"
date
