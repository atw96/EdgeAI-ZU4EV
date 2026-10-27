#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
ls -l /proc/929/fd 2>/dev/null | head -n 40
echo ----
# size of any growing result
find ${EDGEAI_ROOT}/notebooks/hls4ml_prj/myproject_prj/solution1/csim -name '*.log' -o -name '*result*' 2>/dev/null | head
date
