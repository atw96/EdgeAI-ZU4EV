#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
set -euo pipefail
H=${EDGEAI_ROOT}
W=${EDGEAI_ROOT}
# Stop only the 10k csim tree. Leave the board SSH alone.
if [ -d /proc/27 ] && tr '\0' ' ' < /proc/27/cmdline | grep -q v4_csim_10k; then
  kill 27 84 68 69 70 40 43 2>/dev/null || true
  sleep 1
  kill -9 27 84 68 69 70 40 43 2>/dev/null || true
else
  echo "pid 27 is not the csim script; not killing by number"
  pkill -f 'scripts/prepare_gap_csim_tb.py' || true
  pkill -f 'scripts/opt_v2/v4_csim_10k.sh' || true
  pkill -f 'scripts/run_gap_axi_csim.sh' || true
fi
sleep 1
if ps -p 84 >/dev/null 2>&1; then
  echo PREPARE_STILL_ALIVE
  exit 1
fi
cp -f "$W/scripts/prepare_gap_csim_tb.py" "$H/scripts/prepare_gap_csim_tb.py"
cp -f "$W/results/opt_v2/v4_d6.json" "$H/results/opt_v2/v4_d6.json"
chown atw:atw "$H/scripts/prepare_gap_csim_tb.py"
# refuse if a csim is already back
if pgrep -f 'v4_csim_10k.sh' >/dev/null; then
  echo CSIM_STILL
  exit 1
fi
su - atw -c "setsid bash $H/scripts/opt_v2/v4_csim_10k.sh </dev/null >/dev/null 2>&1 & echo RELAUNCHED"
echo OK
