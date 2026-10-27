#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
H=${EDGEAI_ROOT}
echo "==== BOARD ===="
grep -E 'state|KAT|kat|CLOCK|hp0|FAIL|error|refuse|progress|fetched|MD5' "$H/results/opt_v2/logs/v5_board.log" | tail -n 30
echo "==== CSIM ===="
grep -E 'synth csim|csim |Processing|done|ERROR' "$H/results/opt_v2/logs/v5_csim_synth.log" | tail -n 10
wc -l "$H/notebooks/hls4ml_prj/tb_data/csim_results.log" 2>/dev/null || true
ps -ef | grep -E 'csim.exe|v5_board|v5_csim' | grep -v grep | awk '{print $2,$8,$9}' || true
date
