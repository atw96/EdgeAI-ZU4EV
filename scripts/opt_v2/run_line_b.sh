#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
# Line B trainer. Refuses to start unless campaign.py prints next=B1 (board median <= 2 ms).
# Writes new h5 files. Does not overwrite notebooks/model_int8_qkeras.h5.
# 目标主机：wsl-local, conda edgeai_39.
set -euo pipefail
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO"
if [[ "$REPO" == /mnt/* ]]; then
  echo "ERROR: run from ${EDGEAI_ROOT}" >&2
  exit 1
fi

if [[ "${OPT_V2_SKIP_LATENCY_GATE:-0}" == "1" ]]; then
  echo "OPT_V2_SKIP_LATENCY_GATE=1 — start line B without the 2 ms board gate"
else
  next="$(python3 scripts/opt_v2/campaign.py || true)"
  echo "$next"
  case "$next" in
    next=B1*) ;;
    *)
      echo "ERROR: line B is closed ($next)" >&2
      exit 2
      ;;
  esac
fi

source ~/miniconda3/etc/profile.d/conda.sh
conda activate edgeai_39
export PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python

python3 scripts/v19_qat_input_qact_finetune.py \
  --bits 8 --channels 16,20,24 --epochs "${B1_EPOCHS:-40}" \
  --out-h5 notebooks/model_q8_input_qact.h5 \
  --report-json results/opt_v2/b1_q8_finetune.json

python3 scripts/opt_v2/eval_10k.py --stage keras --variant Q6_base --n 10000 \
  --model-h5 notebooks/model_int8_qkeras.h5
python3 scripts/opt_v2/eval_10k.py --stage keras --variant B1_Q8 --n 10000 \
  --model-h5 notebooks/model_q8_input_qact.h5
python3 scripts/opt_v2/mcnemar_pair.py \
  results/opt_v2/correct_Q6_base_keras.npy \
  results/opt_v2/correct_B1_Q8_keras.npy \
  --out results/opt_v2/b1_mcnemar.json

python3 - <<'PY'
import json, sys
doc = json.load(open("results/opt_v2/b1_mcnemar.json"))
gain = doc["top1_c"] - doc["top1_a"]
ok = doc["pvalue"] < 0.05 and gain >= 1.0
print("B1 gain=%.3f p=%.4g ok=%s" % (gain, doc["pvalue"], ok))
sys.exit(0 if ok else 3)
PY

echo "B1 passed McNemar. B2 is a separate invocation: bash scripts/opt_v2/run_line_b.sh --b2"
if [[ "${1:-}" != "--b2" ]]; then
  exit 0
fi

python3 scripts/rf_planner.py --widen 32,32,40,40,48,48 > results/opt_v2/b2_rf_plan.txt
python3 scripts/v19_qat_input_qact_finetune.py \
  --bits "${B2_BITS:-6}" --channels 32,40,48 --epochs "${B2_EPOCHS:-280}" \
  --from-scratch --ema-decay 0.999 \
  --kd-alpha "${B2_KD_ALPHA:-0.5}" --kd-temp "${B2_KD_TEMP:-3.5}" \
  --out-h5 notebooks/model_wide_qkeras.h5 \
  --report-json results/opt_v2/b2_wide_finetune.json
python3 scripts/opt_v2/set_rf.py --variant B2-480
echo "B2 weights written and RF set to B2-480. OUT_DIM=48 OUT_BYTES=192 before the next HLS flow."
