#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
set -eu
M=${EDGEAI_ROOT}
H=${EDGEAI_ROOT}
cp -a "$M/scripts/opt_v2/p1_fix_narrow.sh" "$H/scripts/opt_v2/p1_fix_narrow.sh"
chown atw:atw "$H/scripts/opt_v2/p1_fix_narrow.sh"
chmod +x "$H/scripts/opt_v2/p1_fix_narrow.sh"
su - atw -c "setsid bash $H/scripts/opt_v2/p1_fix_narrow.sh </dev/null >${EDGEAI_ROOT}/results/opt_v2/logs/p1_fix_outer.log 2>&1 & echo STARTED"
echo LAUNCHED
