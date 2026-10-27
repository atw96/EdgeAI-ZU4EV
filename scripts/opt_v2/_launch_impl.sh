#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
set -eu
M=${EDGEAI_ROOT}
H=${EDGEAI_ROOT}
if pgrep -f 'vivado|a1_impl.sh' >/dev/null; then
  echo BUSY
  exit 3
fi
cp -f "$M/scripts/opt_v2/a1_impl.sh" "$H/scripts/opt_v2/a1_impl.sh"
chown atw:atw "$H/scripts/opt_v2/a1_impl.sh"
chmod +x "$H/scripts/opt_v2/a1_impl.sh"
su - atw -c "setsid bash $H/scripts/opt_v2/a1_impl.sh </dev/null >${EDGEAI_ROOT}/results/opt_v2/logs/a1_impl_outer.log 2>&1 & echo STARTED"
echo LAUNCHED
