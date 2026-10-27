#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
set -eu
M=${EDGEAI_ROOT}
H=${EDGEAI_ROOT}
cp -f "$M/scripts/patch_hls_conv_stream.py" "$H/scripts/patch_hls_conv_stream.py"
cp -f "$M/scripts/opt_v2/patch_hls_indexloop.py" "$H/scripts/opt_v2/patch_hls_indexloop.py"
cp -f "$M/scripts/opt_v2/a1_shallow_csynth.sh" "$H/scripts/opt_v2/a1_shallow_csynth.sh"
cp -f "$M/scripts/opt_v2/p5_indexloop.sh" "$H/scripts/opt_v2/p5_indexloop.sh"
cp -f "$M/scripts/opt_v2/p5_after_shallow.sh" "$H/scripts/opt_v2/p5_after_shallow.sh"
chown atw:atw "$H/scripts/patch_hls_conv_stream.py" \
  "$H/scripts/opt_v2/patch_hls_indexloop.py" \
  "$H/scripts/opt_v2/a1_shallow_csynth.sh" \
  "$H/scripts/opt_v2/p5_indexloop.sh" \
  "$H/scripts/opt_v2/p5_after_shallow.sh"
chmod +x "$H/scripts/opt_v2/a1_shallow_csynth.sh" \
  "$H/scripts/opt_v2/p5_indexloop.sh" \
  "$H/scripts/opt_v2/p5_after_shallow.sh"
if pgrep -f vivado_hls >/dev/null; then
  echo VIVADO_BUSY
  exit 3
fi
mkdir -p "$M/results/opt_v2"
cp -f "$H/results/opt_v2/p2b_narrow_p4.json" "$M/results/opt_v2/" || true
cp -f "$H/results/opt_v2/a1_narrow_csynth.json" "$M/results/opt_v2/" || true
cp -f "$H/results/opt_v2/p4_micro_csynth.json" "$M/results/opt_v2/" || true
su - atw -c "setsid bash $H/scripts/opt_v2/a1_shallow_csynth.sh </dev/null >${EDGEAI_ROOT}/results/opt_v2/logs/a1_shallow_outer.log 2>&1 & echo SHALLOW"
su - atw -c "setsid bash $H/scripts/opt_v2/p5_after_shallow.sh </dev/null >${EDGEAI_ROOT}/results/opt_v2/logs/p5_after_outer.log 2>&1 & echo P5WAIT"
echo LAUNCHED
