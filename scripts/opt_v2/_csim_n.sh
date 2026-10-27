#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
H=${EDGEAI_ROOT}
wc -l "$H/notebooks/hls4ml_prj/tb_data/csim_results.log" 2>/dev/null || echo no
ps -p 712 -o etime,pcpu,cmd 2>/dev/null || echo csim_gone
