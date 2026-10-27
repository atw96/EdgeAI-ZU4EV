#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
H=${EDGEAI_ROOT}
tail -n 20 "$H/results/opt_v2/logs/v5_prep_synth.log" 2>/dev/null || echo no_log
ls -l "$H/results/opt_v2/v5_synth/synth_packed.npz" "$H/results/opt_v2/v5_synth/keras_gap.npy" 2>&1 | head
ps -ef | grep v5_prep_synth | grep -v grep || echo prep_done
