#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
set -euo pipefail
H=${EDGEAI_ROOT}
mkdir -p "$H/results/opt_v2/logs"
bash ${EDGEAI_ROOT}/scripts/opt_v2/v5_freeze.sh
setsid bash -c 'source ${HOME}/miniconda3/etc/profile.d/conda.sh && conda activate edgeai_39 && python3 ${EDGEAI_ROOT}/scripts/opt_v2/v5_prep_synth.py' \
  </dev/null >"$H/results/opt_v2/logs/v5_prep_synth.log" 2>&1 &
echo PREP_PID $!
