#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
H=${EDGEAI_ROOT}
M=${EDGEAI_ROOT}
echo ----GATE----
cat "$H/results/opt_v2/a1_shallow_csim_gate.json"
mkdir -p "$M/results/opt_v2"
for f in p2b_narrow_p4.json a1_narrow_csynth.json a1_narrow_attribution.json a1_shallow_csynth.json p4_micro_csynth.json p5_indexloop.json a1_shallow_csim_gate.json p1_narrow_gate.json; do
  if [[ -f "$H/results/opt_v2/$f" ]]; then
    cp -f "$H/results/opt_v2/$f" "$M/results/opt_v2/$f" && echo copied "$f"
  fi
done
