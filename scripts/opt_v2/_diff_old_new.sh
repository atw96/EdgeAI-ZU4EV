#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
H=${EDGEAI_ROOT}
OLD="$H/notebooks/hls4ml_prj.bak_bitexact_opt_v2_A1prime_20261017_092201/firmware"
NEW="$H/results/opt_v2/p1_p4_firmware"
echo "==== defines diff stat ===="
diff -u "$OLD/defines.h" "$NEW/defines.h" | grep -E '^[+-]' | grep -v -E '^[+-]{3}' | head -n 80
echo "==== defines line count ===="
wc -l "$OLD/defines.h" "$NEW/defines.h"
echo "==== nnet diff names ===="
diff -rq "$OLD/nnet_utils" "$H/notebooks/hls4ml_prj.bak_bitexact_p1_p4/firmware/nnet_utils" | head -n 40
echo "==== cpp diff names ===="
diff -rq "$OLD" "$H/notebooks/hls4ml_prj.bak_bitexact_p1_p4/firmware" --exclude weights | head -n 40
