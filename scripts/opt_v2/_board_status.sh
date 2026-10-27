#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
H=${EDGEAI_ROOT}
ps -ef | grep a1_board | grep -v grep | awk '{print $2,$8}' || echo done
echo ----
tail -n 40 "$H/results/opt_v2/logs/a1_board.log" 2>/dev/null || echo no_log
