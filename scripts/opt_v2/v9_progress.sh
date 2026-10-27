#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
H=${EDGEAI_ROOT}
LOG=$H/results/opt_v2/logs/v9_csim_synth.log
if [ -f "$LOG" ]; then
  echo "log_lines $(wc -l < "$LOG")"
  grep -c "Processing input" "$LOG" || true
  tail -n 3 "$LOG"
else
  echo NO_LOG
fi
echo "--- vivado tail ---"
tail -n 5 "$H/results/opt_v2/logs/v9_multiseed.log" 2>/dev/null || true
if [ -f "$H/results/opt_v2/a2l/v9_multiseed.txt" ]; then
  cat "$H/results/opt_v2/a2l/v9_multiseed.txt"
fi
