#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
H=${EDGEAI_ROOT}
echo ----TAIL----
tail -n 20 "$H/results/opt_v2/logs/v4_board_smoke.log"
echo ----OUTER----
tail -n 15 "$H/results/opt_v2/logs/v4_board_py_outer.log"
echo ----NPY----
ls -l "$H/results/opt_v2/smoke_gap.npy" "$H/results/opt_v2/smoke_lat_ms.npy" 2>&1
echo ----CSIM_PS----
ps -ef | grep -E 'csim|vivado_hls|v4_csim' | grep -v grep | awk '{print $2,$8,$9,$10}' | head
echo ----CSIM_LOG----
tail -n 5 "$H/results/opt_v2/logs/v4_csim_10k.log"
