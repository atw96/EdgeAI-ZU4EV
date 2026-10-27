#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
set -euo pipefail
H=${EDGEAI_ROOT}
NEW=$H/notebooks/hls4ml_prj/firmware/defines.h
OLD=$H/notebooks/hls4ml_prj.bak_bitexact_opt_v2_A1prime_20261017_092201/firmware/defines.h
WIDE=$H/notebooks/hls4ml_prj.bak_bitexact_p1_old_a1csynth/firmware/defines.h
echo "cmp new vs old_export: $(cmp -s "$NEW" "$OLD" && echo IDENTICAL || echo DIFFER)"
echo "cmp new vs bitexact: $(cmp -s "$NEW" "$WIDE" && echo IDENTICAL || echo DIFFER)"
echo "---- typedef diff new vs bitexact (first 60) ----"
diff -u "$WIDE" "$NEW" | grep -E '^[+-].*typedef|^[+-].*ap_fixed|^[+-].*ap_ufixed' | head -n 60 || true
echo "---- parameters reuse ----"
grep -n "reuse" "$H/notebooks/hls4ml_prj/firmware/parameters.h" | head -n 30 || true
echo "---- old parameters reuse ----"
grep -n "reuse" "$H/notebooks/hls4ml_prj.bak_bitexact_opt_v2_A1prime_20261017_092201/firmware/parameters.h" | head -n 30 || true
echo "---- weight cmp w3 ----"
cmp -s "$H/notebooks/hls4ml_prj/firmware/weights/w3.h" \
  "$H/notebooks/hls4ml_prj.bak_bitexact_opt_v2_A1prime_20261017_092201/firmware/weights/w3.h" \
  && echo w3 IDENTICAL || echo w3 DIFFER
echo "---- bn typedef samples ----"
grep -n "bn_conv1a" "$NEW" | head
grep -n "bn_conv1a" "$WIDE" | head
