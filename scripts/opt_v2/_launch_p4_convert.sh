#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
set -eu
M=${EDGEAI_ROOT}
H=${EDGEAI_ROOT}
cp -f "$M/scripts/opt_v2/p4_micro_convert.py" "$H/scripts/opt_v2/p4_micro_convert.py"
chown atw:atw "$H/scripts/opt_v2/p4_micro_convert.py"
if pgrep -f p4_micro_convert.sh >/dev/null; then
  echo STILL
  exit 3
fi
su - atw -c "setsid bash $H/scripts/opt_v2/p4_micro_convert.sh </dev/null >${EDGEAI_ROOT}/results/opt_v2/logs/p4_micro_convert_outer.log 2>&1 & echo STARTED"
echo LAUNCHED
