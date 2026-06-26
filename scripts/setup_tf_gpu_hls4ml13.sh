#!/bin/bash
# Enable TensorFlow 2.12 GPU in edgeai_hls4ml13 (WSL2 + RTX 4060).
set -euo pipefail

ENV_NAME="${HLS4ML_ENV:-edgeai_hls4ml13}"
source ~/miniconda3/etc/profile.d/conda.sh
conda activate "$ENV_NAME"

pip install -U 'nvidia-cudnn-cu11==8.6.0.163' 2>&1 | tail -5

ACTD="$CONDA_PREFIX/etc/conda/activate.d"
mkdir -p "$ACTD"
cat > "$ACTD/tf_gpu_env.sh" <<'EOF'
# TensorFlow 2.12 GPU libs (WSL2)
CUDNN_PATH=$(dirname $(python -c "import nvidia.cudnn;print(nvidia.cudnn.__file__)" 2>/dev/null || echo ""))
if [[ -n "$CUDNN_PATH" && -d "$CUDNN_PATH/lib" ]]; then
  export LD_LIBRARY_PATH="${CUDNN_PATH}/lib:${CONDA_PREFIX}/lib:${LD_LIBRARY_PATH:-}"
fi
EOF

source "$ACTD/tf_gpu_env.sh"
python3 <<'PY'
import tensorflow as tf
gpus = tf.config.list_physical_devices("GPU")
print("tensorflow", tf.__version__)
print("GPUs", gpus)
if not gpus:
    raise SystemExit(1)
print("GPU OK:", gpus[0])
PY
