#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
set -eu
M=${EDGEAI_ROOT}
H=${EDGEAI_ROOT}
cp -f "$M/scripts/opt_v2/a1_narrow_csynth.sh" "$H/scripts/opt_v2/a1_narrow_csynth.sh"
cp -f "$M/scripts/opt_v2/a1_after_p2b.sh" "$H/scripts/opt_v2/a1_after_p2b.sh"
chown atw:atw "$H/scripts/opt_v2/a1_narrow_csynth.sh" "$H/scripts/opt_v2/a1_after_p2b.sh"
chmod +x "$H/scripts/opt_v2/a1_narrow_csynth.sh" "$H/scripts/opt_v2/a1_after_p2b.sh"
su - atw -c "setsid bash $H/scripts/opt_v2/a1_after_p2b.sh </dev/null >${EDGEAI_ROOT}/results/opt_v2/logs/a1_after_p2b_outer.log 2>&1 & echo STARTED"
echo LAUNCHED
