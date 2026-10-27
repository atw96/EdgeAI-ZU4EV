#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
H=${EDGEAI_ROOT}
ls -l \
  "$H/notebooks/hls4ml_prj_a2l/myproject_prj/solution1/csim/build/csim.exe" \
  "$H/results/opt_v2/v5_synth/tb_input_features.dat" \
  "$H/results/opt_v2/v5_synth/synth_packed.npz" \
  "$H/results/opt_v2/a2l/cifar10_accel.bit" \
  "$H/deploy/model_int8.tflite" \
  "$H/results/opt_v2/a2l/placed_timing.rpt" 2>&1 | head -30
echo "--- clocks ---"
if [ -f "$H/results/opt_v2/a2l/placed_timing.rpt" ]; then
  grep -n -m 8 "clk_out1\|pl_clk0" "$H/results/opt_v2/a2l/placed_timing.rpt" | head
fi
echo "--- arp ---"
ip -4 addr show | head -20
arp -n | head -40
