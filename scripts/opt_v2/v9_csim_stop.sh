#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
# csim.exe is writing through a symlink into the RC1 HLS tree. Stop it.
pkill -x csim.exe || true
sleep 1
if pgrep -x csim.exe >/dev/null; then
  echo STILL_ALIVE
  pgrep -a csim.exe
else
  echo CSIM_STOPPED
fi
H=${EDGEAI_ROOT}
echo "=== rc1 csim log ==="
ls -l --time-style=full-iso "$H/notebooks/hls4ml_prj/tb_data/csim_results.log" 2>&1
wc -l "$H/notebooks/hls4ml_prj/tb_data/csim_results.log" 2>&1
echo "=== other copies ==="
find "$H/results" "$H/notebooks/hls4ml_prj" "$H/notebooks/hls4ml_prj_a2l" -name 'csim_results.log' -o -name '*csim_gap*' -o -name '*csim.log' 2>/dev/null | head -40
