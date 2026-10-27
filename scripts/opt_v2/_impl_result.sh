#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
H=${EDGEAI_ROOT}
echo ----WNS----
grep -n -E "Worst Negative Slack|Timing PASSED|Timing FAILED|BUILD SUCCESS|ERROR:|WNS" "$H/results/opt_v2/logs/a1_impl.log" | tail -40
echo ----PARKED----
ls -lh "$H/deploy/opt_v2/A1shallow/" 2>/dev/null || echo empty
md5sum "$H/deploy/opt_v2/A1shallow/"* 2>/dev/null || true
echo ----GOLDEN----
md5sum "$H/deploy/cifar10_accel.bit"
echo ----UTIL----
grep -n -E "CLB LUTs|Block RAM Tile|DSPs|Slice LUTs" "$H/impl_build.log" | head -20
