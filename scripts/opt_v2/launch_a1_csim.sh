#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
# Detach A1' csim. Target host: wsl-local. Does not SSH to the board.
set -eu
REPO=${EDGEAI_ROOT}
LOG="$REPO/results/opt_v2/logs/A1prime_csim_flow.log"
PIDF="$REPO/results/opt_v2/logs/a1_csim.pid"
BASE="$REPO/results/opt_v2/baseline_csim_results.log"
P4="$REPO/notebooks/hls4ml_prj.bak_bitexact_opt_v2_A1prime_20261017_092201/tb_data/csim_results.log"
mkdir -p "$(dirname "$LOG")"
if [[ ! -f "$BASE" ]]; then
  cp "$P4" "$BASE"
  echo "seeded P4 csim baseline ($(wc -l < "$BASE") lines)"
fi
if [[ -f "$PIDF" ]]; then
  old="$(cat "$PIDF" || true)"
  if [[ -n "${old}" ]] && kill -0 "$old" 2>/dev/null; then
    echo "already running pid=$old"
    exit 0
  fi
fi
setsid bash -c "cd '$REPO' && export VARIANT=A1prime STAGE=csim OPT_V2_SKIP_MCP=1 SKIP_BOARD=1 N_CSIM=1000 && exec bash scripts/opt_v2/run_opt_v2_flow.sh" >"$LOG" 2>&1 </dev/null &
echo $! >"$PIDF"
echo "STARTED pid=$(cat "$PIDF") log=$LOG"
