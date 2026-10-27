#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
H=${EDGEAI_ROOT}
OUT=$H/results/opt_v2/a2l/synth729_golden.bin
for i in $(seq 1 60); do
  if [ -f "$OUT" ]; then
    echo CSIM_READY
    wc -c "$OUT"
    exit 0
  fi
  if ! pgrep -x csim.exe >/dev/null; then
    echo CSIM_DEAD
    tail -n 20 "$H/results/opt_v2/logs/v9_csim_synth.log"
    exit 1
  fi
  sleep 20
done
echo CSIM_TIMEOUT
exit 2
