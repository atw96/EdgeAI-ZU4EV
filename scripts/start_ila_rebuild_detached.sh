#!/bin/bash
# Detached launcher — survives WSL/Cursor shell exit
REPO="/home/atw/Edge_AI_Acc/claude/EdgeAI-ZU4EV_Claude"
cd "$REPO" || exit 1
if pgrep -f "run_ila_output_rebuild.sh" >/dev/null 2>&1; then
  echo "already running"
  exit 0
fi
setsid bash "$REPO/scripts/run_ila_output_rebuild.sh" \
  >>"$REPO/results/ila_output_rebuild.log" 2>&1 < /dev/null &
echo "started pid=$!"
