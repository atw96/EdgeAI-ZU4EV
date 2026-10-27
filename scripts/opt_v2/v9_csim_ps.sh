#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
if pgrep -x csim.exe >/dev/null; then
  ps -o etime,time,pcpu -C csim.exe
else
  echo NO_CSIM
  tail -n 8 ${EDGEAI_ROOT}/results/opt_v2/logs/v9_csim_synth.log
fi
