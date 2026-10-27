#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
H=${EDGEAI_ROOT}
LOG=$H/results/opt_v2/logs/v9_r5.log
if [ -f "$LOG" ]; then
  echo "LOG_BYTES $(wc -c < "$LOG")"
  echo "---- tail ----"
  tail -n 40 "$LOG"
else
  echo "NO_LOG"
fi
echo "---- procs ----"
pgrep -af 'v9_r5|v9_cpu|csim.exe' || echo NO_MATCHING_PROCS
