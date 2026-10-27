#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
# Detach B1 so the WSL session can exit. Target host: wsl-local, user atw.
set -eu
REPO=${EDGEAI_ROOT}
LOG="$REPO/results/opt_v2/logs/b1_q8_train.log"
PIDF="$REPO/results/opt_v2/logs/b1_q8.pid"
mkdir -p "$(dirname "$LOG")"
if [[ -f "$PIDF" ]]; then
  old="$(cat "$PIDF" || true)"
  if [[ -n "${old}" ]] && kill -0 "$old" 2>/dev/null; then
    echo "already running pid=$old"
    exit 0
  fi
fi
setsid bash -c "cd '$REPO' && export OPT_V2_SKIP_LATENCY_GATE=1 && exec bash scripts/opt_v2/run_line_b.sh" >"$LOG" 2>&1 </dev/null &
echo $! >"$PIDF"
echo "STARTED pid=$(cat "$PIDF") log=$LOG"
