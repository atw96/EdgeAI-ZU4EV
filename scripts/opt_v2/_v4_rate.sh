#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
H=${EDGEAI_ROOT}
echo "---- board ----"
grep progress "$H/results/opt_v2/logs/v4_board_10k.log" | tail -n 5
echo "---- csim lines ----"
LOG=$(find "$H/notebooks/hls4ml_prj/myproject_prj" -name csim_results.log -o -name csim.log 2>/dev/null | head)
echo "found $LOG"
if [ -n "$LOG" ]; then wc -l "$LOG"; tail -n 2 "$LOG"; fi
echo "---- csim tail ----"
tail -n 3 "$H/results/opt_v2/logs/v4_csim_10k.log"
date
ps -ef | grep -E 'csim.exe|board_10k.py' | grep -v grep | awk '{print $2,$8,$9}' || true
