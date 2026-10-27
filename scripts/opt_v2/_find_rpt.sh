#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
H=${EDGEAI_ROOT}
find "$H/notebooks" -name 'myproject_axi_csynth.rpt' 2>/dev/null | head -20
