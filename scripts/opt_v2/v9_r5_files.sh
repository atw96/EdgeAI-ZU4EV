#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
H=${EDGEAI_ROOT}
echo "=== /tmp/v9_stage ==="
ls -lh /tmp/v9_stage 2>&1 | head -40
echo "=== repo bits ==="
ls -lh \
  "$H/results/opt_v2/a2l/cifar10_accel.bit" \
  "$H/deploy/opt_v2/A1shallow/cifar10_accel.bit" \
  "$H/results/opt_v2/bench10k_packed.npz" \
  "$H/results/opt_v2/v5_v2/board_gap_v2_rc1.npy" \
  "$H/scripts/dma_infer_common.py" \
  "$H/scripts/board_load_only.sh" \
  "$H/scripts/board_fix_hp0_width.py" \
  ${EDGEAI_ROOT}/scripts/opt_v2/v8_x1.py \
  ${EDGEAI_ROOT}/scripts/opt_v2/v9_r5.py \
  2>&1
