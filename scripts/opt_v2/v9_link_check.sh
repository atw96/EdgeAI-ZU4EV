#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
H=${EDGEAI_ROOT}
LINK=$H/notebooks/hls4ml_prj_a2l/myproject_prj/solution1/csim/build/tb_data
if [ -L "$LINK" ]; then
  echo "SYMLINK $(readlink "$LINK")"
else
  echo "NOT_A_SYMLINK"
  ls -ld "$LINK"
fi
wc -l "$H/notebooks/hls4ml_prj/tb_data/csim_results.log"
