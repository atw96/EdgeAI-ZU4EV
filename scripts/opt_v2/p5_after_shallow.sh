#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
set -euo pipefail
H=${EDGEAI_ROOT}
echo "[$(date '+%F %T')] waiting for shallow A1' csynth"
for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
  if pgrep -f 'a1_shallow_csynth.sh' >/dev/null; then
    break
  fi
  if [[ -f "$H/results/opt_v2/a1_shallow_csynth.json" ]]; then
    break
  fi
  sleep 2
done
while pgrep -f 'a1_shallow_csynth.sh|vivado_hls' >/dev/null; do
  sleep 20
done
if [[ ! -f "$H/results/opt_v2/a1_shallow_csynth.json" ]]; then
  echo "shallow json missing" >&2
  exit 4
fi
echo "[$(date '+%F %T')] starting P5"
exec bash "$H/scripts/opt_v2/p5_indexloop.sh"
