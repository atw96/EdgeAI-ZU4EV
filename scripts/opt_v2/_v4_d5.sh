#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
# Local typedef diff. No HLS, no SSH.
set -euo pipefail
H=${EDGEAI_ROOT}
NEW=$H/notebooks/hls4ml_prj/firmware/defines.h
OLD=$H/notebooks/hls4ml_prj.bak_bitexact_opt_v2_A1prime_20261017_092201/firmware/defines.h
WIDE=$H/notebooks/hls4ml_prj.bak_bitexact_p1_old_a1csynth/firmware/defines.h
echo "==== new vs deployed-export-era (narrow) ===="
diff -u "$OLD" "$NEW" | head -n 120 || true
echo "==== new vs BIT_EXACT=1 A1' ===="
if [ -f "$WIDE" ]; then
  diff -u "$WIDE" "$NEW" | rg -n "ap_fixed|ap_ufixed|typedef" | head -n 80 || true
fi
echo "==== RF lines ===="
rg -n "reuse_factor|conv1a" "$H/notebooks/hls4ml_prj/firmware/parameters.h" | head -n 20 || true
rg -n "reuse" "$NEW" | head || true
