#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
H=${EDGEAI_ROOT}
W=${EDGEAI_ROOT}
cp -f "$H/results/opt_v2/v4_d6.json" "$W/results/opt_v2/v4_d6.json"
echo ----BOARD----
tail -n 12 "$H/results/opt_v2/logs/v4_board_10k.log"
echo ----CSIMCPU----
ps -p 84 -o etime,pcpu,cmd 2>/dev/null || echo prepare_done
tail -n 4 "$H/results/opt_v2/logs/v4_csim_10k.log"
