#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
H=${EDGEAI_ROOT}
PRJ="$H/notebooks/hls4ml_prj/myproject_prj/solution1"
echo ----FIND----
find "$PRJ" -iname '*util*' -o -iname '*synth*' -o -iname '*export*.rpt' | head -40
echo ----LOG----
grep -n -E "synth_design|Utilization|Finished RTL|Failed|BRAM|LUT" "$H/results/opt_v2/logs/a1_shallow_csynth.log" | head -40
