#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
# Detach A1' csynth. Target host: wsl-local. No board access.
set -eu
REPO=${EDGEAI_ROOT}
LOG="$REPO/results/opt_v2/logs/A1prime_csynth_flow.log"
PIDF="$REPO/results/opt_v2/logs/a1_csynth.pid"
mkdir -p "$(dirname "$LOG")"
if [[ -f "$PIDF" ]]; then
  old="$(cat "$PIDF" || true)"
  if [[ -n "${old}" ]] && kill -0 "$old" 2>/dev/null; then
    echo "already running pid=$old"
    exit 0
  fi
fi
setsid bash -c "cd '$REPO' && export VARIANT=A1prime STAGE=csynth OPT_V2_SKIP_MCP=1 && exec bash scripts/opt_v2/run_opt_v2_flow.sh" >"$LOG" 2>&1 </dev/null &
echo $! >"$PIDF"
echo "STARTED pid=$(cat "$PIDF") log=$LOG"
