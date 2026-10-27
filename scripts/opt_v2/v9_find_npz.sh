#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
H=${EDGEAI_ROOT}
find "$H/deploy" "$H/results" "$H/notebooks" -name '*.npz' -printf '%s %p\n' 2>/dev/null | sort -n | awk '$1 > 1000000 {print}' | head -40
