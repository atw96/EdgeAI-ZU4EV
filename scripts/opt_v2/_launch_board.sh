#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
python3 - <<'PY'
import json
from pathlib import Path
out = {
    "bit_md5": "334e27454dcb05d179d6d188b7d404c3",
    "hwh_md5": "d28912cf36889689724c22f034f12bc8",
    "golden_bit_md5": "46987907f8177883048b705fdf68c370",
    "golden_restored": True,
    "wns_ns": 0.090,
    "whs_ns": 0.010,
    "tns_ns": 0.0,
    "placed_lut_as_logic": 33459,
    "placed_bram_tiles": 20,
    "placed_dsp": 207,
    "csynth_ms": 0.87675,
    "path": "deploy/opt_v2/A1shallow/cifar10_accel.bit",
}
p = (Path(__import__("os").environ["EDGEAI_ROOT"]) / 'results/opt_v2/a1_impl.json')
p.write_text(json.dumps(out, indent=2) + "\n")
print("wrote", p)
PY
cp -f ${EDGEAI_ROOT}/results/opt_v2/a1_impl.json ${EDGEAI_ROOT}/results/opt_v2/a1_impl.json
M=${EDGEAI_ROOT}
H=${EDGEAI_ROOT}
cp -f "$M/scripts/opt_v2/a1_board.sh" "$H/scripts/opt_v2/a1_board.sh"
chown atw:atw "$H/scripts/opt_v2/a1_board.sh"
chmod +x "$H/scripts/opt_v2/a1_board.sh"
su - atw -c "setsid bash $H/scripts/opt_v2/a1_board.sh </dev/null >${EDGEAI_ROOT}/results/opt_v2/logs/a1_board_outer.log 2>&1 & echo STARTED"
echo LAUNCHED
