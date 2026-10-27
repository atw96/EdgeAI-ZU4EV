#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
H=${EDGEAI_ROOT}
ps -ef | grep -iE 'vivado|xsim|hw_server' | grep -v grep || echo no_vivado
echo ----LCK----
find "$H/vivado_project" -name '*.lck' -o -name '*.lock' 2>/dev/null | head
echo ----FUSER----
fuser -v "$H/vivado_project/EdgeAI_ZU4EV.runs" 2>&1 | head -30 || true
ls -ld "$H/vivado_project/EdgeAI_ZU4EV.runs" 2>/dev/null || echo no_runs
