#!/bin/bash
# Re-export HLS IP with myproject_axi top (reuse v7 CNN RTL, reset=0 incremental),
# then rebuild bitstream + board benchmark.
set -euo pipefail

REPO="/home/atw/Edge_AI_Acc/claude/EdgeAI-ZU4EV_Claude"
LOG="${REPO}/results/axi_ip_export_bit.log"
VIVADO_HLS="/tools/Xilinx/Vivado/2020.1/bin/vivado_hls"

exec > >(tee -a "$LOG") 2>&1
log() { echo "[$(date '+%F %T')] $*"; }

log "=== axi IP export + bit (reuse v7 CNN, top=myproject_axi) ==="

# Stop any stale Vivado jobs
pkill -9 -f 'vivado|vrs|rebuild_bitstream|run_impl_and_bitstream' 2>/dev/null || true
sleep 2

source ~/miniconda3/etc/profile.d/conda.sh
conda activate edgeai_39
cd "$REPO"

export OUTPUT_AXIS_BITS=32 OUTPUT_PACK_MODE=slot AXI_DATAFLOW=0
export DENSE_MULT_PARTITION_FACTOR="${DENSE_MULT_PARTITION_FACTOR:-16}"
export HLS_ARRAY_PARTITION_MAX="${HLS_ARRAY_PARTITION_MAX:-4096}"

python3 scripts/patch_dense_partition.py
python3 scripts/patch_hls_axi_top.py
python3 scripts/patch_axi_wrapper.py
python3 scripts/patch_axi_testbench.py

HLS="${REPO}/notebooks/hls4ml_prj"
TEST_BAK="${HLS}/myproject_test.cpp.bak_axiexp"
[[ -f "${HLS}/myproject_test.cpp" && ! -f "$TEST_BAK" ]] && mv "${HLS}/myproject_test.cpp" "$TEST_BAK"

export LIBRARY_PATH="/usr/lib/x86_64-linux-gnu:${LIBRARY_PATH:-}"
conda deactivate
cd "$HLS"
log "--- HLS incremental export: reset=0 synth=1 export=1 (keep v7 autopilot db) ---"
$VIVADO_HLS -f build_prj.tcl reset=0 csim=0 synth=1 cosim=0 validation=0 export=1
cd "$REPO"
[[ -f "$TEST_BAK" ]] && mv "$TEST_BAK" "${HLS}/myproject_test.cpp"

IP_ZIP="${HLS}/myproject_prj/solution1/impl/ip/xilinx_com_hls_myproject_axi_1_0.zip"
IP_LEGACY="${HLS}/myproject_prj/solution1/impl/ip/xilinx_com_hls_myproject_1_0.zip"
if [[ -f "$IP_ZIP" ]]; then
  log "OK: exported $IP_ZIP"
elif [[ -f "$IP_LEGACY" ]]; then
  log "ERROR: still exported legacy myproject IP — check set_top patch"
  exit 1
else
  log "ERROR: no HLS IP zip under impl/ip/"
  exit 1
fi

source ~/miniconda3/etc/profile.d/conda.sh
conda activate edgeai_39
source /tools/Xilinx/Vivado/2020.1/settings64.sh
export FORCE_REBUILD=1 HLS_OUTPUT_AXIS_BITS=32
rm -rf "${REPO}/vivado_project/.cache/ip" 2>/dev/null || true
bash scripts/rebuild_bitstream.sh --no-sync

NEW=$(md5sum deploy/cifar10_accel.bit | awk '{print $1}')
log "New bit MD5=$NEW"

ssh-keygen -f "$HOME/.ssh/known_hosts" -R "${BOARD_IP:-192.168.1.40}" 2>/dev/null || true
export OUT_DIM=24 OUT_BYTES=92 OUT_LAYOUT=gap_ps OUT_FIXED_SCALE=256
bash scripts/board_auto_fix.sh

sshpass -p "${BOARD_PASS:-root}" ssh -o StrictHostKeyChecking=no "root@${BOARD_IP:-192.168.1.40}" \
  "cd /tmp/edgeai_bench && OUT_DIM=24 OUT_BYTES=92 OUT_LAYOUT=gap_ps OUT_FIXED_SCALE=256 N_ACCURACY=100 python3 -u board_benchmark.py" \
  | tee "${REPO}/results/gap_only_board_v8.log"

N_GAP_COMPARE=10 BOARD_IP="${BOARD_IP:-192.168.1.40}" BOARD_PASS="${BOARD_PASS:-root}" \
  bash scripts/run_gap_axi_csim.sh

log "=== axi IP export + bit DONE ==="
