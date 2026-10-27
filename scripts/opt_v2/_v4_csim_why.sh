#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
H=${EDGEAI_ROOT}
echo ----PROC----
ps -ef | grep -E 'v4_csim|run_gap|vivado_hls|csim' | grep -v grep || echo none
echo ----LOGTAIL----
tail -n 40 "$H/results/opt_v2/logs/v4_csim_10k.log"
echo ----GAPLOG----
tail -n 30 "$H/results/gap_axi_csim_board.log" 2>/dev/null || echo no_gaplog
echo ----D6FILE----
ls -l "$H/results/opt_v2/v4_d6.json" 2>/dev/null || echo no_d6
