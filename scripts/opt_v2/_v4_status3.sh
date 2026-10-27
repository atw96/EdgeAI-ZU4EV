#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
H=${EDGEAI_ROOT}
echo ----10K----
tail -n 15 "$H/results/opt_v2/logs/v4_board_10k.log" 2>/dev/null || echo none
echo ----D6----
tail -n 30 "$H/results/opt_v2/logs/v4_d6.log" 2>/dev/null || echo none
echo ----CSIM----
tail -n 6 "$H/results/opt_v2/logs/v4_csim_10k.log" 2>/dev/null || echo none
ps -ef | grep -E 'csim.exe|vivado_hls|board_10k|v4_d6' | grep -v grep | awk '{print $2,$8,$9,$10}' | head
