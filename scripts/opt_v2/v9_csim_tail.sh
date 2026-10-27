#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
H=${EDGEAI_ROOT}
LOG=$H/results/opt_v2/logs/v9_csim_synth.log
python3 - << 'PY'
from collections import Counter
p=__import__("os").environ["EDGEAI_ROOT"] + '/results/opt_v2/logs/v9_csim_synth.log'
c=Counter()
n=0
last=[]
with open(p, errors="replace") as f:
    for line in f:
        n+=1
        key=line.strip()[:80]
        if key.startswith("WARNING"):
            c["WARNING"]+=1
        else:
            c["OTHER"]+=1
            last.append(key)
print("lines", n, "warn", c["WARNING"], "other", c["OTHER"])
print("--- last nonwarn ---")
for x in last[-20:]:
    print(x)
PY
echo "--- tb ---"
find "$H/notebooks/hls4ml_prj_a2l" -name '*test*.cpp' -o -name 'myproject_test.cpp' | head
