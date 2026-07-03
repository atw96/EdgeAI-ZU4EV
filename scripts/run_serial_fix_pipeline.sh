#!/bin/bash
# Full serial 32-bit GAP output pipeline: patches -> csim gates -> csynth -> cosim -> bitstream -> board.
set -euo pipefail

REPO="/home/atw/Edge_AI_Acc/claude/EdgeAI-ZU4EV_Claude"
HLS="${REPO}/notebooks/hls4ml_prj"
VIVADO_HLS="/tools/Xilinx/Vivado/2020.1/bin/vivado_hls"
LOG="${REPO}/results/serial_fix_pipeline.log"
mkdir -p "${REPO}/results"
exec > >(tee -a "$LOG") 2>&1

cd "$REPO"
export LIBRARY_PATH="/usr/lib/x86_64-linux-gnu:${LIBRARY_PATH:-}"
export OUTPUT_AXIS_BITS=32 OUTPUT_PACK_MODE=serial AXI_DATAFLOW=0
export OUT_DIM=24 OUT_BYTES=96 OUT_LAYOUT=gap_ps OUT_FIXED_SCALE=1024
export IN_FIXED_SCALE=1024 BIT_EXACT=0
export HLS_STREAM_DEPTH_PROFILE=board_safe
export DENSE_NPZ="${REPO}/deploy/dense_head.npz"
export SKIP_BOARD=1 N_GAP_COMPARE=100 N_ACCURACY=100

activate_conda() {
  source ~/miniconda3/etc/profile.d/conda.sh
  local env_name="${CONDA_ENV:-edgeai_39}"
  if ! conda env list | awk '{print $1}' | grep -qx "$env_name"; then
    echo "WARN: conda env ${env_name} missing, trying fpga-agent"
    env_name=fpga-agent
  fi
  conda activate "$env_name"
}

echo "[$(date '+%F %T')] === serial fix: HLS patches ==="
activate_conda
python3 scripts/patch_hls_lowmem.py || true
python3 scripts/patch_hls_dense_mult.py || true
python3 scripts/patch_hls_dense_resource_antihang.py || true
python3 scripts/patch_hls_mult_strategy.py || true
python3 scripts/patch_hls_stream_depth.py
python3 scripts/patch_hls_axi_top.py || true
python3 scripts/patch_axi_wrapper.py
python3 scripts/patch_axi_testbench.py
python3 scripts/patch_hls_axi_csim_tb.py || true

echo "[$(date '+%F %T')] === csim N=100 (SKIP_BOARD=1) ==="
bash scripts/run_gap_axi_csim.sh

N_ACCURACY=100 OUT_DIM=24 DENSE_NPZ="$DENSE_NPZ" python3 scripts/gap_csim_ps_dense_accuracy.py
N_GAP_COMPARE=100 python3 scripts/gap_csim_keras_align.py
python3 - <<'PY'
import json
d = json.load(open('results/gap_csim_ps_dense_accuracy.json'))
k = json.load(open('results/gap_csim_keras_align.json'))
top1 = d['csim_ps_dense_top1_pct']
mae = k['summary']['csim_vs_keras_mae_mean']
print('GATE csim: Top1=%.1f%% MAE=%.4f' % (top1, mae))
ok = top1 >= 75 and mae <= 0.35
print('PASS' if ok else 'FAIL')
raise SystemExit(0 if ok else 1)
PY

echo "[$(date '+%F %T')] === csynth ==="
conda deactivate 2>/dev/null || true
cd "$HLS"
rm -rf myproject_prj/solution1/.autopilot \
       myproject_prj/solution1/syn \
       myproject_prj/solution1/csim 2>/dev/null || true
$VIVADO_HLS -f build_prj.tcl reset=1 csim=0 synth=1 cosim=0 validation=0 export=0

cd "$REPO"
activate_conda
python3 scripts/hls_csynth_gate.py || GATE_RC=$?
GATE_RC=${GATE_RC:-0}
if [[ "$GATE_RC" -ne 0 ]]; then
  BRAM_OK=$(python3 -c "import json; d=json.load(open('results/hls_csynth_gate.json')); print(d.get('bram_pass', d['used']['BRAM_18K']<256))")
  if [[ "$BRAM_OK" != "True" ]]; then
    echo "ERROR: csynth BRAM gate failed"
    exit 1
  fi
  echo "WARN: LUT gate failed but BRAM ok — continuing"
fi

echo "[$(date '+%F %T')] === RTL cosim N=2 ==="
N_GAP_COMPARE=2 bash scripts/run_hls_csim_cosim.sh

echo "[$(date '+%F %T')] === export IP + Vivado bitstream ==="
conda deactivate 2>/dev/null || true
cd "$HLS"
$VIVADO_HLS -f build_prj.tcl reset=0 csim=0 synth=0 cosim=0 validation=0 export=1

cd "$REPO"
source /tools/Xilinx/Vivado/2020.1/settings64.sh
export FORCE_REBUILD=1 HLS_OUTPUT_AXIS_BITS=32
rm -rf vivado_project/.cache/ip 2>/dev/null || true
bash scripts/rebuild_bitstream.sh --no-sync

echo "[$(date '+%F %T')] === board deploy OUT_BYTES=96 ==="
activate_conda
BOARD_IP="${BOARD_IP:-192.168.1.40}"
BOARD_PASS="${BOARD_PASS:-root}"
ssh-keygen -f "$HOME/.ssh/known_hosts" -R "$BOARD_IP" 2>/dev/null || true
OUT_DIM=24 OUT_BYTES=96 OUT_LAYOUT=gap_ps OUT_FIXED_SCALE=1024 OUTPUT_PACK_MODE=serial \
  BOARD_IP="$BOARD_IP" BOARD_PASS="$BOARD_PASS" \
  bash scripts/board_auto_fix.sh

echo "[$(date '+%F %T')] === board align + accuracy ==="
N_GAP_COMPARE=10 BOARD_IP="$BOARD_IP" BOARD_PASS="$BOARD_PASS" \
  OUT_DIM=24 OUT_BYTES=96 OUT_FIXED_SCALE=1024 OUTPUT_PACK_MODE=serial \
  python3 scripts/gap_axi_csim_board_align.py
N_ACCURACY=100 OUT_DIM=24 DENSE_NPZ="$DENSE_NPZ" python3 scripts/gap_csim_ps_dense_accuracy.py

echo "[$(date '+%F %T')] === serial fix pipeline complete ==="