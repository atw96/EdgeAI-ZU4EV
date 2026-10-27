#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
source ${HOME}/miniconda3/etc/profile.d/conda.sh
conda activate edgeai_39
python3 ${EDGEAI_ROOT}/docs/event_stats.py \
  c_rc2_149:0:10000000
python3 - << 'PY'
import json
from pathlib import Path
import numpy as np
H = Path(__import__("os").environ["EDGEAI_ROOT"])
pack = np.load(H / "results/opt_v2/bench10k_packed.npz")
labels = np.asarray(pack["labels"])
gap = np.load(H / "results/opt_v2/v5_v2/board_gap_v2_rc1.npy")
dense = np.load(H / "deploy/dense_head.npz")
pred = ((gap.astype(np.float32) / 1024.0) @ dense["weight"] + dense["bias"]).argmax(1)
acc = float((pred == labels).mean())
print("fpga_top1", acc, "n", len(labels))
doc = {
    "rc2_md5": "395160123c39a98d478e598c9f93e39e",
    "rc1_md5": "334e27454dcb05d179d6d188b7d404c3",
    "old_md5": "46987907f8177883048b705fdf68c370",
    "fpga_top1_vs_labels": acc,
    "synth729": {
        "a2l_csim_vs_rc1_csim_max_abs_lsb": 0,
        "board_vs_rc1_csim_max_lsb": 0,
        "board_events": 0,
        "board_wait_ms": 0.3840,
        "note": "A2-L csim equals the RC1 csim of the same 729 frames, and the board equals that golden, so the board equals the A2-L csim.",
    },
    "soak_10m": {
        "seen": 10000000,
        "tail_timeout": 0,
        "diff_10us": 0,
        "bad_immediate": 0,
        "bad_10us": 0,
        "bad_1ms": 0,
        "delay_max_ns": 30630,
        "elapsed_s": 4218.085,
        "garwood_95_upper_per_million": 0.3689,
        "clock_end": "0x01010a02",
        "temp_c": {
            "ps_start": 36.71, "ps_end": 36.39,
            "remote_start": 34.97, "remote_end": 35.80,
            "pl_start": 35.19, "pl_end": 35.01,
        },
    },
    "timing_5ns": {
        "performance_explore_wns_ns": 0.048111,
        "defaults_wns_ns": -0.284842,
        "spreadlogic_high_wns_ns": -0.017798,
        "explore_postroute_route_wns_ns": 0.045757,
        "note": "Defaults and SpreadLogic_high miss 5 ns. Explore and the route step of ExplorePostRoutePhysOpt meet it. The shipped bitstream is the Explore run.",
    },
    "timing_6p667": {
        "method": "set_clock_uncertainty -setup -1.667 because PERIOD of the generated clock is read-only",
        "reported_requirement_ns": 5.0,
        "reported_wns_ns": 1.715,
        "equivalent_operating_slack_ns": 1.715,
    },
    "ab_c_harness_10k_x3": {
        "old_99.94": {"wait_ms": 57.1075, "hot_ms": 57.1225, "events": 0, "max_lsb": 0, "reps": 3},
        "rc1_99.94": {"wait_ms": 1.6838, "hot_ms": 1.6982, "events": 0, "max_lsb": 0, "reps": 3},
        "rc1_149.9": {"wait_ms": 1.1229, "hot_ms": 1.1365, "events": 0, "max_lsb": 0, "reps": 3},
        "rc2_99.94": {"wait_ms": 0.5757, "hot_ms": 0.5897, "events": 0, "max_lsb": 0, "reps": 3},
        "rc2_149.9": {"wait_ms": 0.3840, "hot_ms": 0.3972, "events": 0, "max_lsb": 0, "reps": 3},
        "repeat_note": "The three medians of each cell printed identically at 0.0001 ms.",
        "same_clock_wait_ratio_old_over_rc2": round(57.1075 / 0.5757, 2),
        "best_config_wait_ratio_old_over_rc2": round(57.1075 / 0.3840, 2),
        "same_clock_hot_ratio_old_over_rc2": round(57.1225 / 0.5897, 2),
        "best_config_hot_ratio_old_over_rc2": round(57.1225 / 0.3972, 2),
    },
    "power_w": "未测",
}
(H / "results/opt_v2/v9_fpga.json").write_text(json.dumps(doc, indent=2) + "\n")
print("wrote", H / "results/opt_v2/v9_fpga.json")
PY
