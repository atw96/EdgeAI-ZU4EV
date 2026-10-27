#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
set -eu
M=${EDGEAI_ROOT}
H=${EDGEAI_ROOT}
cp -a "$M/scripts/opt_v2/p1_narrow_1k.sh" "$H/scripts/opt_v2/p1_narrow_1k.sh"
chown atw:atw "$H/scripts/opt_v2/p1_narrow_1k.sh"
chmod +x "$H/scripts/opt_v2/p1_narrow_1k.sh"
su - atw -c "setsid bash $H/scripts/opt_v2/p1_narrow_1k.sh </dev/null >${EDGEAI_ROOT}/results/opt_v2/logs/p1_narrow_1k_outer.log 2>&1 & echo STARTED"
echo LAUNCHED
