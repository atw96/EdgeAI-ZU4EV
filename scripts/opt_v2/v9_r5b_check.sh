#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
H=${EDGEAI_ROOT}
pgrep -af v9_r5_restage || echo NO_RESTAGE
echo "---- log ----"
tail -n 30 "$H/results/opt_v2/logs/v9_r5b.log" 2>/dev/null || echo NO_LOG
echo "---- nohup ----"
tail -n 15 "$H/results/opt_v2/logs/v9_r5b.nohup" 2>/dev/null || echo NO_NOHUP
