#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
set -eu
H=${EDGEAI_ROOT}
grep -E 'conv1a_accum|bn_conv1a_scale|bn_conv1a_bias|input_t' "$H/notebooks/hls4ml_prj/firmware/defines.h" | head
