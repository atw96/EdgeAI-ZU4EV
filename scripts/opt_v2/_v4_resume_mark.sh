#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
H=${EDGEAI_ROOT}
grep -E 'resume wrote|combined|ERROR|Traceback|top1|board vs csim|extreme|resume done|decision' \
  "$H/results/opt_v2/logs/v4_resume_csim.log" | tail -n 30
echo "==== ps ===="
ps -ef | grep -E 'p1_numeric|v4_resume|csim.exe' | grep -v grep || echo none
date
