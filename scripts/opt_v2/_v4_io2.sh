#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
H=${EDGEAI_ROOT}
echo "---- dat ----"
ls -lh "$H/notebooks/hls4ml_prj/tb_data/tb_input_features.dat"
echo "---- csim log ----"
tail -n 8 "$H/results/opt_v2/logs/v4_csim_10k.log"
echo "---- board log ----"
tail -n 8 "$H/results/opt_v2/logs/v4_board_10k.log"
echo "---- procs ----"
ps -ef | grep -E 'prepare_gap|v4_csim|board_10k.py|ssh -o' | grep -v grep | awk '{print $2,$8,$9,$10,$11}' | head -n 20
date
