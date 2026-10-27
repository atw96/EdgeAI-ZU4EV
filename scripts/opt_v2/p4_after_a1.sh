#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
# Start the eight micro csynths only after narrow A1' csynth has written its json.
# Target host: wsl-local.
set -euo pipefail
H=${EDGEAI_ROOT}
echo "[$(date '+%F %T')] waiting for narrow A1' csynth json"
while [[ ! -f "$H/results/opt_v2/a1_narrow_csynth.json" ]]; do
  sleep 30
done
while pgrep -f 'vivado_hls|a1_narrow_csynth.sh' >/dev/null; do
  sleep 15
done
echo "[$(date '+%F %T')] starting P4 micro csynth"
exec bash "$H/scripts/opt_v2/p4_micro_csynth.sh"
