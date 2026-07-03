#!/bin/bash
# Serial GAP board deploy + csim align + accuracy gates.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"
mkdir -p results

source ~/miniconda3/etc/profile.d/conda.sh
conda activate edgeai_39

export BOARD_IP="${BOARD_IP:-192.168.1.40}"
export BOARD_PASS="${BOARD_PASS:-root}"
export OUT_DIM=24 OUT_BYTES=96 OUT_LAYOUT=gap_ps OUT_FIXED_SCALE=1024 OUTPUT_PACK_MODE=serial
export DENSE_NPZ="${REPO}/deploy/dense_head.npz"

echo "[$(date '+%F %T')] === board deploy (serial) ==="
bash scripts/board_auto_fix.sh 2>&1 | tee results/serial_board_deploy.log

echo "[$(date '+%F %T')] === csim N=100 (SKIP_BOARD=1) ==="
SKIP_BOARD=1 N_GAP_COMPARE=100 bash scripts/run_gap_axi_csim.sh

echo "[$(date '+%F %T')] === board vs csim align N=10 ==="
N_GAP_COMPARE=10 python3 scripts/gap_axi_csim_board_align.py

echo "[$(date '+%F %T')] === csim+PS dense accuracy N=100 ==="
N_ACCURACY=100 python3 scripts/gap_csim_ps_dense_accuracy.py

python3 - <<'PY'
import json
from pathlib import Path

align_p = Path('results/gap_axi_csim_board_align.json')
acc_p = Path('results/gap_csim_ps_dense_accuracy.json')
bench_p = Path('results/fpga_benchmark.json')

align = json.loads(align_p.read_text(encoding='utf-8'))
acc = json.loads(acc_p.read_text(encoding='utf-8'))
bench = json.loads(bench_p.read_text(encoding='utf-8')) if bench_p.is_file() else {}

s = align.get('summary', {})
gap_mae = s.get('gap_mae_mean')
beat_match = s.get('beat_word_match_mean_pct')
board_top1 = acc.get('board_top1_pct')
csim_top1 = acc.get('csim_ps_dense_top1_pct')
fpga_top1 = bench.get('accuracy_top1')

print('=== GATE SUMMARY (serial board verify) ===')
print('gap_mae_mean:', gap_mae)
print('beat_word_match_mean_pct:', beat_match)
print('board_top1_pct:', board_top1)
print('csim_top1_pct:', csim_top1)
print('fpga_benchmark accuracy_top1:', fpga_top1)
print('align summary JSON:', json.dumps(s, indent=2))
PY