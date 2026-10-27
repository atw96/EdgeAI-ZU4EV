#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
H=${EDGEAI_ROOT}
echo ----BOARD----
tail -n 30 "$H/results/opt_v2/logs/v4_board_smoke.log" 2>/dev/null || echo no_board
echo ----CSIM----
tail -n 8 "$H/results/opt_v2/logs/v4_csim_10k.log" 2>/dev/null || echo no_csim
ps -ef | grep -E 'v4_board|v4_csim|csim.exe' | grep -v grep | awk '{print $2,$8,$9}' || echo none
