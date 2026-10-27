#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
set -euo pipefail
H=${EDGEAI_ROOT}
mkdir -p "$H/results/opt_v2/logs"
if pgrep -f v5_board_kat_synth.sh >/dev/null; then
  echo ALREADY
  exit 0
fi
setsid bash ${EDGEAI_ROOT}/scripts/opt_v2/v5_board_kat_synth.sh \
  </dev/null >"$H/results/opt_v2/logs/v5_board_outer.log" 2>&1 &
echo STARTED
sleep 2
wc -c "$H/results/opt_v2/logs/v5_board_outer.log" "$H/results/opt_v2/logs/v5_board.log" 2>/dev/null || true
ps -ef | grep v5_board_kat | grep -v grep || echo not_running
