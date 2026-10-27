#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
# Wait until the P2b csynth process exits, then start narrow A1' csynth.
# Target host: wsl-local.
set -euo pipefail
H=${EDGEAI_ROOT}
echo "[$(date '+%F %T')] waiting for p2b"
while pgrep -f 'p2b_narrow_p4.sh' >/dev/null; do
  sleep 20
done
# vivado can outlive the shell for a moment
while pgrep -f 'vivado_hls' >/dev/null; do
  sleep 10
done
if [[ ! -f "$H/results/opt_v2/p2b_narrow_p4.json" ]]; then
  echo "P2b json missing" >&2
  exit 4
fi
echo "[$(date '+%F %T')] p2b json ready, starting A1 csynth"
exec bash "$H/scripts/opt_v2/a1_narrow_csynth.sh"
