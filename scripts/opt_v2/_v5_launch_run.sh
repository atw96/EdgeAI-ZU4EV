#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
set -euo pipefail
H=${EDGEAI_ROOT}
source ${HOME}/miniconda3/etc/profile.d/conda.sh
conda activate edgeai_39
python3 ${EDGEAI_ROOT}/scripts/opt_v2/v5_build_kat.py
setsid bash ${EDGEAI_ROOT}/scripts/opt_v2/v5_csim_synth.sh </dev/null >/dev/null 2>&1 &
echo CSIM $!
setsid bash ${EDGEAI_ROOT}/scripts/opt_v2/v5_board_kat_synth.sh </dev/null >/dev/null 2>&1 &
echo BOARD $!
