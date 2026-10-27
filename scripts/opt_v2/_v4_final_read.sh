#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
H=${EDGEAI_ROOT}
echo "==== extreme ===="
cat "$H/results/opt_v2/v4_extreme_csim.txt" 2>/dev/null || echo missing
echo "==== d3 decision ===="
python3 -c 'import json; d=json.load(open("'"$H"'/results/opt_v2/v4_d3.json")); print(d["decision"]); print("n", d["results"]["n"], "mae", d["results"]["mae_a1"], "pass", d["results"]["pass"])'
echo "==== e2e ===="
python3 -c 'import json; d=json.load(open("'"$H"'/results/opt_v2/e2e_report.json")); print("hard", d["pass_hard_gate"]); print("gap", d["gap_board_vs_csim"]); print("top1", d["top1"]); print("delta_pt", d["board_vs_keras_top1_gap_pt"]); print("lat", d["latency_ms"]["median"], d["latency_ms"]["p99"])'
echo "==== log tail ===="
tail -n 25 "$H/results/opt_v2/logs/v4_resume_csim.log"
echo "==== windows copies ===="
ls -l ${EDGEAI_ROOT}/results/opt_v2/v4_d3.json ${EDGEAI_ROOT}/results/opt_v2/v4_extreme_csim.txt ${EDGEAI_ROOT}/results/opt_v2/e2e_report.json
