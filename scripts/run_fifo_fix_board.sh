#!/bin/bash
# Gate 4: export IP + rebuild bit + board verify after cosim pass.
set -euo pipefail

REPO="/home/atw/Edge_AI_Acc/claude/EdgeAI-ZU4EV_Claude"
HLS="${REPO}/notebooks/hls4ml_prj"
VIVADO_HLS="/tools/Xilinx/Vivado/2020.1/bin/vivado_hls"
BOARD_IP="${BOARD_IP:-192.168.1.40}"
BOARD_PASS="${BOARD_PASS:-root}"
N_ACCURACY="${N_ACCURACY:-100}"
MIN_TOP1="${MIN_TOP1:-75}"

cd "$REPO"
export LIBRARY_PATH="/usr/lib/x86_64-linux-gnu:${LIBRARY_PATH:-}"
export OUTPUT_AXIS_BITS=32 OUTPUT_PACK_MODE=serial AXI_DATAFLOW=0
export OUT_DIM=24 OUT_BYTES=96 OUT_LAYOUT=gap_ps OUT_FIXED_SCALE=1024
export IN_FIXED_SCALE=1024
export DENSE_NPZ="${REPO}/deploy/dense_head.npz"

OLD=$(md5sum deploy/cifar10_accel.bit 2>/dev/null | awk '{print $1}')
echo "[$(date '+%F %T')] old bit MD5=$OLD"

echo "[$(date '+%F %T')] === export IP ==="
conda deactivate 2>/dev/null || true
cd "$HLS"
$VIVADO_HLS -f build_prj.tcl reset=0 csim=0 synth=0 cosim=0 validation=0 export=1

echo "[$(date '+%F %T')] === Vivado rebuild ==="
cd "$REPO"
source /tools/Xilinx/Vivado/2020.1/settings64.sh
export FORCE_REBUILD=1 HLS_OUTPUT_AXIS_BITS=32
rm -rf vivado_project/.cache/ip 2>/dev/null || true
bash scripts/rebuild_bitstream.sh --no-sync

NEW=$(md5sum deploy/cifar10_accel.bit | awk '{print $1}')
echo "[$(date '+%F %T')] new bit MD5=$NEW"

echo "[$(date '+%F %T')] === board deploy ==="
source ~/miniconda3/etc/profile.d/conda.sh
conda activate edgeai_39
ssh-keygen -f "$HOME/.ssh/known_hosts" -R "$BOARD_IP" 2>/dev/null || true
OUT_DIM=24 OUT_BYTES=96 OUT_LAYOUT=gap_ps OUT_FIXED_SCALE=1024 \
  BOARD_IP="$BOARD_IP" BOARD_PASS="$BOARD_PASS" \
  bash scripts/board_auto_fix.sh 2>&1 | tee results/v19_fifo_fix_board.log

echo "[$(date '+%F %T')] === board align + accuracy ==="
N_GAP_COMPARE=10 BOARD_IP="$BOARD_IP" BOARD_PASS="$BOARD_PASS" \
  OUT_DIM=24 OUT_BYTES=96 OUT_FIXED_SCALE=1024 \
  python3 scripts/gap_axi_csim_board_align.py

N_ACCURACY="$N_ACCURACY" OUT_DIM=24 DENSE_NPZ="$DENSE_NPZ" \
  python3 scripts/gap_csim_ps_dense_accuracy.py

python3 - <<PY
import json
d = json.load(open('results/gap_csim_ps_dense_accuracy.json'))
a = json.load(open('results/gap_axi_csim_board_align.json'))
board_top1 = d.get('board_top1_pct')
csim_top1 = d.get('csim_ps_dense_top1_pct')
mae = a.get('summary', {}).get('gap_mae_mean', a.get('gap_mae_mean'))
match_pct = a.get('summary', {}).get('writable_slot_match_pct', a.get('writable_slot_match_pct'))
print('board Top1=%.1f%% csim Top1=%.1f%% GAP MAE=%s match%%=%s' % (
    board_top1 or -1, csim_top1 or -1, mae, match_pct))
ok = (board_top1 or 0) >= $MIN_TOP1
print('PASS' if ok else 'FAIL')
raise SystemExit(0 if ok else 1)
PY
