#!/bin/bash
# Isolated env for hls4ml 1.x + QKeras bit_exact (does NOT touch edgeai_39 / Vivado flow).
set -euo pipefail

ENV_NAME="${HLS4ML_ENV:-edgeai_hls4ml13}"
LOG="${1:-/home/atw/Edge_AI_Acc/claude/EdgeAI-ZU4EV_Claude/results/v19_hls4ml13_setup.log}"

exec > >(tee -a "$LOG") 2>&1
log() { echo "[$(date '+%F %T')] $*"; }

source ~/miniconda3/etc/profile.d/conda.sh

if conda env list | awk '{print $1}' | grep -qx "$ENV_NAME"; then
  log "conda env $ENV_NAME already exists — skip create"
else
  log "Creating conda env $ENV_NAME (python=3.10)..."
  conda create -n "$ENV_NAME" python=3.10 -y
fi

conda activate "$ENV_NAME"

log "Installing HDF5/h5py via conda-forge (avoid pip libhdf5 build failure)..."
conda install -y -c conda-forge h5py

log "Installing hls4ml[qkeras]==1.3.0 stack (pinned TF 2.12 + tfmo 0.7.5)..."
pip install -U pip wheel setuptools
pip install \
  'hls4ml[qkeras]==1.3.0' \
  'tensorflow==2.12.0' \
  'tensorflow-model-optimization==0.7.5' \
  'qkeras==0.9.0' \
  'numpy>=1.22,<1.25' \
  'sympy>=1.13.1' \
  matplotlib pandas seaborn scikit-learn tqdm

log "--- import smoke test ---"
python3 <<'PY'
import hls4ml, qkeras, tensorflow as tf
print("hls4ml", hls4ml.__version__)
print("qkeras", qkeras.__version__)
print("tensorflow", tf.__version__)
gpus = tf.config.list_physical_devices("GPU")
print("GPUs:", gpus)
import hls4ml.model.profiling as p
print("profiling compare:", hasattr(p, "compare"))
print("profiling numerical:", hasattr(p, "numerical"))
PY

log "=== setup_hls4ml13_env DONE ==="
