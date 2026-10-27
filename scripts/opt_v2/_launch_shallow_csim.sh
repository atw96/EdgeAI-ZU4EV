#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
set -eu
M=${EDGEAI_ROOT}
H=${EDGEAI_ROOT}
cp -f "$M/scripts/opt_v2/a1_shallow_csim.sh" "$H/scripts/opt_v2/a1_shallow_csim.sh"
chown atw:atw "$H/scripts/opt_v2/a1_shallow_csim.sh"
chmod +x "$H/scripts/opt_v2/a1_shallow_csim.sh"
su - atw -c "setsid bash $H/scripts/opt_v2/a1_shallow_csim.sh </dev/null >${EDGEAI_ROOT}/results/opt_v2/logs/a1_shallow_csim_outer.log 2>&1 & echo CSIMWAIT"
echo LAUNCHED
