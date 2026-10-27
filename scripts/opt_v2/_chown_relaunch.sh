#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
set -eu
H=${EDGEAI_ROOT}
# Vivado as atw cannot delete a root-owned runs directory, so create_project -force aborts.
chown -R atw:atw "$H/vivado_project"
echo chowned
ls -ld "$H/vivado_project" "$H/vivado_project/EdgeAI_ZU4EV.runs"
if pgrep -f a1_impl.sh >/dev/null; then
  echo STILL
  exit 3
fi
su - atw -c "setsid bash $H/scripts/opt_v2/a1_impl.sh </dev/null >${EDGEAI_ROOT}/results/opt_v2/logs/a1_impl_outer.log 2>&1 & echo STARTED"
echo LAUNCHED
