#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
set -eu
M=${EDGEAI_ROOT}
H=${EDGEAI_ROOT}
cp -f "$M/scripts/opt_v2/p2b_narrow_p4.sh" "$H/scripts/opt_v2/p2b_narrow_p4.sh"
chown atw:atw "$H/scripts/opt_v2/p2b_narrow_p4.sh"
chmod +x "$H/scripts/opt_v2/p2b_narrow_p4.sh"
mkdir -p "$M/results/opt_v2"
cp -f "$H/results/opt_v2/p1_narrow_gate.json" "$M/results/opt_v2/p1_narrow_gate.json"
cp -f "$H/results/opt_v2/p1_narrow_static_diff.json" "$M/results/opt_v2/p1_narrow_static_diff.json" || true
cp -f "$H/results/opt_v2/p1_narrow_p4_n100.json" "$M/results/opt_v2/p1_narrow_p4_n100.json" || true
if pgrep -f 'p1_narrow_1k.sh' >/dev/null; then
  echo STILL_BUSY
  exit 3
fi
su - atw -c "setsid bash $H/scripts/opt_v2/p2b_narrow_p4.sh </dev/null >${EDGEAI_ROOT}/results/opt_v2/logs/p2b_narrow_p4_outer.log 2>&1 & echo STARTED"
echo LAUNCHED
