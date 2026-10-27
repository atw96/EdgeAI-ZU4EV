#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
# Convert the four P4 microbench projects. No Vivado. Target host: wsl-local.
set -euo pipefail
REPO=${EDGEAI_ROOT}
cd "$REPO"
LOG="$REPO/results/opt_v2/logs/p4_micro_convert.log"
mkdir -p "$REPO/results/opt_v2/logs"
exec > >(tee -a "$LOG") 2>&1
echo "[$(date '+%F %T')] P4 micro convert"
source ${HOME}/miniconda3/etc/profile.d/conda.sh
conda activate edgeai_hls4ml13
export PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python
python3 -u scripts/opt_v2/p4_micro_convert.py
echo "[$(date '+%F %T')] P4 micro convert done"
