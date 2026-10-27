#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
set -eu
M=${EDGEAI_ROOT}
H=${EDGEAI_ROOT}
cp -f "$M/scripts/opt_v2/libfakerev.c" "$H/scripts/opt_v2/libfakerev.c"
cp -f "$M/scripts/opt_v2/a1_shallow_syn.sh" "$H/scripts/opt_v2/a1_shallow_syn.sh"
chown atw:atw "$H/scripts/opt_v2/libfakerev.c" "$H/scripts/opt_v2/a1_shallow_syn.sh"
chmod +x "$H/scripts/opt_v2/a1_shallow_syn.sh"
su - atw -c "setsid bash $H/scripts/opt_v2/a1_shallow_syn.sh </dev/null >${EDGEAI_ROOT}/results/opt_v2/logs/a1_shallow_syn_outer.log 2>&1 & echo SYNWAIT"
echo LAUNCHED
