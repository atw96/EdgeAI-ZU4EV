#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
H=${EDGEAI_ROOT}
echo ----PROCS----
ps -ef | grep -E 'a1_impl|vivado' | grep -v grep | awk '{print $2,$8,$9,$10}' | head -15 || echo none
echo ----MD5----
md5sum "$H/deploy/cifar10_accel.bit" "$H/deploy/opt_v2/golden_locked/cifar10_accel.bit" 2>/dev/null || echo no_snap
echo ----TAIL----
tail -n 25 "$H/results/opt_v2/logs/a1_impl.log" 2>/dev/null || echo no_log
