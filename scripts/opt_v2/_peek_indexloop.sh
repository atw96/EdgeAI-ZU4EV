#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
# Show the IndexLoop body in the unpatched hls4ml 1.3 header.
H=${EDGEAI_ROOT}
f=$(find "$H/notebooks/hls4ml_prj.bak_bitexact_p1_old_a1csynth" -name 'nnet_dense_resource.h' | head -1)
echo "FILE $f"
python3 - <<PY
from pathlib import Path
p = Path("$f")
text = p.read_text(errors="replace")
key = "dense_resource_rf_gt_nin_rem0"
i = text.find(key)
print("idx", i)
print(text[i:i+2500])
PY
