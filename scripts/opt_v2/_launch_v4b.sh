#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
set -euo pipefail
H=${EDGEAI_ROOT}
W=${EDGEAI_ROOT}
cp -f "$W/scripts/opt_v2/board_10k.py" "$H/scripts/opt_v2/board_10k.py"
cp -f "$W/scripts/opt_v2/v4_board_10k.sh" "$H/scripts/opt_v2/v4_board_10k.sh"
cp -f "$W/scripts/opt_v2/v4_d6.py" "$H/scripts/opt_v2/v4_d6.py"
chown atw:atw "$H/scripts/opt_v2/board_10k.py" "$H/scripts/opt_v2/v4_board_10k.sh" "$H/scripts/opt_v2/v4_d6.py"
chmod +x "$H/scripts/opt_v2/v4_board_10k.sh"
if pgrep -af 'v4_board_10k|board_10k.py' | grep -v pgrep >/dev/null; then
  echo BUSY
  exit 1
fi
su - atw -c "setsid bash $H/scripts/opt_v2/v4_board_10k.sh </dev/null >/dev/null 2>&1 & echo BOARD10K"
su - atw -c "setsid bash -c 'source ${HOME}/miniconda3/etc/profile.d/conda.sh && conda activate edgeai_39 && python3 $H/scripts/opt_v2/v4_d6.py' </dev/null >$H/results/opt_v2/logs/v4_d6.log 2>&1 & echo D6"
echo LAUNCHED
