#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
# Place and route the shallow-FIFO A1' IP. The deployed bit is restored on exit.
# Target host: wsl-local.
set -euo pipefail
REPO=${EDGEAI_ROOT}
WIN=${EDGEAI_ROOT}
SNAP=$REPO/deploy/opt_v2/golden_locked
OUT=$REPO/deploy/opt_v2/A1shallow
LOG=$REPO/results/opt_v2/logs/a1_impl.log
mkdir -p "$SNAP" "$OUT" "$REPO/results/opt_v2/logs"
cd "$REPO"

golden_md5=$(md5sum "$REPO/deploy/cifar10_accel.bit" | awk '{print $1}')
if [[ "$golden_md5" != 46987907f8177883048b705fdf68c370 ]]; then
  echo "refuse: deploy bit is not the golden image ($golden_md5)" >&2
  exit 2
fi
cp -f "$REPO/deploy/cifar10_accel.bit" "$SNAP/cifar10_accel.bit"
cp -f "$REPO/deploy/cifar10_accel.hwh" "$SNAP/cifar10_accel.hwh"
if [[ -f "$REPO/deploy/cifar10_accel.xsa" ]]; then
  cp -f "$REPO/deploy/cifar10_accel.xsa" "$SNAP/cifar10_accel.xsa"
fi

restore_golden() {
  cp -f "$SNAP/cifar10_accel.bit" "$REPO/deploy/cifar10_accel.bit"
  cp -f "$SNAP/cifar10_accel.hwh" "$REPO/deploy/cifar10_accel.hwh"
  if [[ -f "$SNAP/cifar10_accel.xsa" ]]; then
    cp -f "$SNAP/cifar10_accel.xsa" "$REPO/deploy/cifar10_accel.xsa"
  fi
  if [[ -d "$WIN/deploy" ]]; then
    cp -f "$SNAP/cifar10_accel.bit" "$WIN/deploy/cifar10_accel.bit" || true
    cp -f "$SNAP/cifar10_accel.hwh" "$WIN/deploy/cifar10_accel.hwh" || true
  fi
  now=$(md5sum "$REPO/deploy/cifar10_accel.bit" | awk '{print $1}')
  echo "golden restored $now"
}

park_new_bit() {
  if [[ ! -f "$REPO/deploy/cifar10_accel.bit" ]]; then
    return 0
  fi
  local md5
  md5=$(md5sum "$REPO/deploy/cifar10_accel.bit" | awk '{print $1}')
  if [[ "$md5" == 46987907f8177883048b705fdf68c370 ]]; then
    echo "deploy bit still golden, nothing to park"
    return 0
  fi
  cp -f "$REPO/deploy/cifar10_accel.bit" "$OUT/cifar10_accel.bit"
  cp -f "$REPO/deploy/cifar10_accel.hwh" "$OUT/cifar10_accel.hwh" || true
  cp -f "$REPO/deploy/cifar10_accel.xsa" "$OUT/cifar10_accel.xsa" 2>/dev/null || true
  cp -f "$REPO/deploy/cifar10_accel.ltx" "$OUT/cifar10_accel.ltx" 2>/dev/null || true
  echo "parked new bit $md5 -> $OUT"
}

finish() {
  park_new_bit
  restore_golden
}
trap finish EXIT

exec > >(tee -a "$LOG") 2>&1
echo "[$(date '+%F %T')] impl A1shallow, golden locked"
test -f "$REPO/notebooks/hls4ml_prj/myproject_prj/solution1/impl/ip/component.xml"
source /tools/Xilinx/Vivado/2020.1/settings64.sh
export FORCE_REBUILD=1
export HLS_OUTPUT_AXIS_BITS=32
export VIVADO_JOBS=8
bash scripts/rebuild_bitstream.sh --no-sync
echo "[$(date '+%F %T')] impl script returned"
grep -n "Worst Negative Slack\|Timing PASSED\|Timing FAILED\|BUILD SUCCESS\|ERROR:" "$LOG" | tail -20 || true
