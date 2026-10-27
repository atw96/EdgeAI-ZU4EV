#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
H=${EDGEAI_ROOT}
echo "--- bins ---"
find "$H" ${HOME} -maxdepth 3 -name 'v8_x2_hot' -o -name 'v8_x3' -o -name 'bench_payloads.bin' -o -name 'dense_w.bin' 2>/dev/null | head -40
echo "--- data ---"
ls -l \
  "$H/deploy/opt_v2/A1shallow/cifar10_accel.bit" \
  "$H/deploy/cifar10_accel.bit" \
  "$H/results/opt_v2/a2l/cifar10_accel.bit" \
  "$H/deploy/dense_head.npz" \
  "$H/results/opt_v2/v5_synth/kat_packed.npz" \
  "$H/results/opt_v2/v5_synth/kat_golden.npz" \
  "$H/results/opt_v2/bench10k_packed.npz" \
  "$H/results/opt_v2/v5_v2/board_gap_v2_rc1.npy" \
  "$H/results/opt_v2/v5_synth/synth_packed.npz" \
  2>&1 | head -30
