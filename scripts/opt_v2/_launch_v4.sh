#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
set -eu
M=${EDGEAI_ROOT}
H=${EDGEAI_ROOT}
cp -f "$M/scripts/opt_v2/board_smoke8.py" "$H/scripts/opt_v2/board_smoke8.py"
cp -f "$M/scripts/opt_v2/v4_board_smoke.sh" "$H/scripts/opt_v2/v4_board_smoke.sh"
cp -f "$M/scripts/opt_v2/v4_csim_10k.sh" "$H/scripts/opt_v2/v4_csim_10k.sh"
chown atw:atw "$H/scripts/opt_v2/board_smoke8.py" "$H/scripts/opt_v2/v4_board_smoke.sh" "$H/scripts/opt_v2/v4_csim_10k.sh"
chmod +x "$H/scripts/opt_v2/v4_board_smoke.sh" "$H/scripts/opt_v2/v4_csim_10k.sh"
if pgrep -f 'vivado_hls|v4_csim_10k|v4_board_smoke' >/dev/null; then
  echo BUSY
  exit 3
fi
su - atw -c "setsid bash $H/scripts/opt_v2/v4_csim_10k.sh </dev/null >${EDGEAI_ROOT}/results/opt_v2/logs/v4_csim_10k_outer.log 2>&1 & echo CSIM"
su - atw -c "setsid bash $H/scripts/opt_v2/v4_board_smoke.sh </dev/null >${EDGEAI_ROOT}/results/opt_v2/logs/v4_board_smoke_outer.log 2>&1 & echo BOARD"
echo LAUNCHED
