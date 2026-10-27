#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
H=${EDGEAI_ROOT}
echo "=== parent ==="
pgrep -af v9_csim || echo NO_PARENT
echo "=== a2l tb ==="
wc -l "$H/notebooks/hls4ml_prj_a2l/tb_data/tb_input_features.dat" "$H/notebooks/hls4ml_prj_a2l/tb_data/tb_output_predictions.dat" "$H/notebooks/hls4ml_prj_a2l/tb_data/csim_results.log" 2>&1
ls -l "$H/notebooks/hls4ml_prj_a2l/tb_data/"*.v9bak 2>&1 | head
echo "=== saved logs ==="
wc -l "$H/results/opt_v2/a2l/csim_results.log" "$H/results/opt_v2/a1_shallow_csim.log" "$H/results/opt_v2/v5_synth/csim_results.log" "$H/results/opt_v2/v5_synth/tb_output_predictions.dat" 2>&1
echo "=== df ==="
df -h /tmp ${HOME} | head
