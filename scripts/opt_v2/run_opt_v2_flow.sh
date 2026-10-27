#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
# One v2 variant: convert -> Route1 patches -> csim -> csynth -> optional impl/deploy.
# RF table must already be in scripts/v19_hls_config_common.py (see set_rf.py).
# 目标主机：wsl-local. Board steps ssh to axu4ev-board from wsl-local only.
#
# Required stamps (written only after MCP precompile_guard ok=true):
#   results/opt_v2/mcp_hls_ok
#   results/opt_v2/mcp_vivado_ok
#   results/opt_v2/mcp_board_ok
set -euo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
VARIANT="${VARIANT:?set VARIANT}"
STAGE="${STAGE:-convert}"
N_CSIM="${N_CSIM:-1000}"
BOARD_IP="${BOARD_IP:?BOARD_IP}"
BOARD_PASS="${BOARD_PASS:?BOARD_PASS}"
HLS="${REPO}/notebooks/hls4ml_prj"
LOG_DIR="${REPO}/results/opt_v2/logs"
mkdir -p "$LOG_DIR" "${REPO}/results/opt_v2/archive" "${REPO}/deploy/opt_v2/${VARIANT}" "${REPO}/deploy/baseline"

if [[ "$REPO" == /mnt/* ]]; then
  echo "ERROR: 目标主机 wsl-local 必须使用 ${EDGEAI_ROOT} ，不要用 ${REPO}" >&2
  exit 1
fi

log() { echo "[$(date '+%F %T')] [opt_v2 ${VARIANT} ${STAGE}] $*"; }

require_stamp() {
  local stamp="$1"
  # 2026-10-17: 用户确认 path-env-guard 不支持 Vivado 2020.1，本流程允许 OPT_V2_SKIP_MCP=1。
  if [[ "${OPT_V2_SKIP_MCP:-0}" == "1" ]]; then
    echo "OPT_V2_SKIP_MCP=1 — skip ${stamp}"
    return 0
  fi
  if [[ ! -f "${REPO}/results/opt_v2/${stamp}" ]]; then
    echo "ERROR: missing results/opt_v2/${stamp}. Call MCP precompile_guard and touch it only when ok=true." >&2
    exit 1
  fi
}

archive_file() {
  local src="$1"
  if [[ -f "$src" ]]; then
    cp -n "$src" "${REPO}/results/opt_v2/archive/$(basename "$src").$(date +%Y%m%dT%H%M%S)" || true
  fi
}

export BIT_EXACT=1
export GAP_ONLY=1
export OUTPUT_AXIS_BITS=32
export OUTPUT_PACK_MODE=serial
export AXI_DATAFLOW=0
export OUT_DIM="${OUT_DIM:-24}"
export OUT_BYTES="${OUT_BYTES:-96}"
export OUT_LAYOUT=gap_ps
export OUT_FIXED_SCALE=1024
export IN_FIXED_SCALE=1024
export OPT_V2_KEEP_RF=1
export DENSE_NPZ="${REPO}/deploy/dense_head.npz"
export PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python

source ~/miniconda3/etc/profile.d/conda.sh
cd "$REPO"

snapshot_golden_bit() {
  if [[ -f deploy/cifar10_accel.bit ]]; then
    local md5
    md5="$(md5sum deploy/cifar10_accel.bit | awk '{print $1}')"
    case "$md5" in
      46987907*)
        cp -n deploy/cifar10_accel.bit deploy/baseline/cifar10_accel.bit || true
        cp -n deploy/cifar10_accel.hwh deploy/baseline/cifar10_accel.hwh || true
        log "snapshotted golden bit ${md5}"
        ;;
    esac
  fi
}

stage_convert() {
  conda activate edgeai_hls4ml13
  export BAK_TAG="opt_v2_${VARIANT}_$(date +%Y%m%d_%H%M%S)"
  local logf="${LOG_DIR}/${VARIANT}_convert.log"
  python3 scripts/v19_bitexact_convert.py 2>&1 | tee "$logf"
  if grep -n "Invalid ReuseFactor" "$logf"; then
    echo "ERROR: hls4ml rewrote an illegal ReuseFactor" >&2
    exit 1
  fi
  conda deactivate || true
}

stage_patch() {
  conda activate edgeai_39
  python3 scripts/patch_hls_rf_v14.py
  python3 scripts/patch_hls_restore_dataflow.py
  python3 scripts/patch_hls_conv_stream.py || true
  python3 scripts/patch_hls_conv_cyclic_restore.py || true
  python3 scripts/patch_hls_stream_depth.py
  python3 scripts/patch_hls_dense_mult.py
  python3 scripts/patch_hls_dense_antihang.py
  python3 scripts/patch_hls_dense_resource_antihang.py
  python3 scripts/patch_hls_mult_strategy.py
  python3 scripts/patch_hls_axi_top.py || true
  python3 scripts/patch_axi_wrapper.py
  python3 scripts/patch_axi_testbench.py
  python3 scripts/patch_hls_axi_csim_tb.py || true
  if ! grep -n "#pragma HLS DATAFLOW" "${HLS}/firmware/"*.cpp; then
    echo "ERROR: top-level DATAFLOW pragma missing after patches" >&2
    exit 1
  fi
  conda deactivate || true
}

stage_csim() {
  conda activate edgeai_39
  archive_file "${REPO}/results/gap_csim_ps_dense_accuracy.json"
  N_GAP_COMPARE="$N_CSIM" N_ACCURACY="$N_CSIM" bash scripts/run_gap_axi_csim.sh \
    2>&1 | tee "${LOG_DIR}/${VARIANT}_csim.log"
  local base="${REPO}/results/opt_v2/baseline_csim_results.log"
  local cur="${HLS}/tb_data/csim_results.log"
  if [[ ! -f "$base" ]]; then
    cp "$cur" "$base"
    log "saved csim baseline (no prior log to compare)"
  elif [[ "${VARIANT}" != "P4" ]]; then
    python3 scripts/opt_v2/bitexact_gap_compare.py "$base" "$cur" --n "$N_CSIM"
  fi
  conda deactivate || true
}

stage_csynth() {
  require_stamp mcp_hls_ok
  conda deactivate >/dev/null 2>&1 || true
  # shellcheck disable=SC1091
  source /tools/Xilinx/Vivado/2020.1/settings64.sh
  cd "$HLS"
  rm -rf myproject_prj/solution1/.autopilot \
         myproject_prj/solution1/syn \
         myproject_prj/solution1/csim 2>/dev/null || true
  /tools/Xilinx/Vivado/2020.1/bin/vivado_hls -f build_prj.tcl reset=1 csim=0 synth=1 cosim=0 validation=0 export=0 \
    2>&1 | tee "${LOG_DIR}/${VARIANT}_csynth.log"
  /tools/Xilinx/Vivado/2020.1/bin/vivado_hls -f build_prj.tcl reset=0 csim=0 synth=0 cosim=0 validation=0 export=1 \
    2>&1 | tee -a "${LOG_DIR}/${VARIANT}_csynth.log"
  cd "$REPO"
  conda activate edgeai_39
  archive_file "${REPO}/results/hls_csynth_gate.json"
  python3 scripts/hls_csynth_gate.py || true
  python3 scripts/opt_v2/parse_csynth_layers.py \
    --out "${REPO}/results/opt_v2/csynth_layers.json"
  conda deactivate || true
}

stage_impl() {
  require_stamp mcp_vivado_ok
  snapshot_golden_bit
  conda deactivate >/dev/null 2>&1 || true
  # shellcheck disable=SC1091
  source /tools/Xilinx/Vivado/2020.1/settings64.sh
  export FORCE_REBUILD=1 HLS_OUTPUT_AXIS_BITS=32
  rm -rf vivado_project/.cache/ip 2>/dev/null || true
  bash scripts/rebuild_bitstream.sh --no-sync 2>&1 | tee "${LOG_DIR}/${VARIANT}_impl.log"
  cp -f deploy/cifar10_accel.bit "deploy/opt_v2/${VARIANT}/cifar10_accel.bit"
  cp -f deploy/cifar10_accel.hwh "deploy/opt_v2/${VARIANT}/cifar10_accel.hwh"
  log "bit md5 $(md5sum deploy/cifar10_accel.bit | awk '{print $1}')"
}

stage_deploy() {
  require_stamp mcp_board_ok
  local ssh_opts=(-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=8)
  sshpass -p "$BOARD_PASS" ssh "${ssh_opts[@]}" "root@${BOARD_IP}" "mkdir -p /tmp/edgeai_bench"
  sshpass -p "$BOARD_PASS" scp "${ssh_opts[@]}" \
    scripts/dma_infer_common.py scripts/slot32_layout.py scripts/board_fetch_gap.py \
    scripts/board_load_only.sh scripts/board_fix_hp0_width.py scripts/board_latency_compare.py \
    deploy/cifar10_accel.bit deploy/cifar10_accel.hwh deploy/dense_head.npz \
    "root@${BOARD_IP}:/tmp/edgeai_bench/"
  if [[ -f deploy/cifar10_bench_1k.npz ]]; then
    sshpass -p "$BOARD_PASS" scp "${ssh_opts[@]}" deploy/cifar10_bench_1k.npz \
      "root@${BOARD_IP}:/tmp/edgeai_bench/cifar10_bench.npz"
  fi
  sshpass -p "$BOARD_PASS" ssh "${ssh_opts[@]}" "root@${BOARD_IP}" \
    "cp /tmp/edgeai_bench/cifar10_accel.bit /lib/firmware/cifar10_accel.bit && \
     chmod +x /tmp/edgeai_bench/board_load_only.sh && \
     FORCE_PL_RELOAD=1 sh /tmp/edgeai_bench/board_load_only.sh && \
     timeout 45 cat /sys/class/fpga_manager/fpga0/state"
  local env="OUT_DIM=${OUT_DIM} OUT_BYTES=${OUT_BYTES} OUT_LAYOUT=gap_ps OUT_FIXED_SCALE=1024 OUTPUT_PACK_MODE=serial DENSE_NPZ=dense_head.npz BENCH_NPZ=cifar10_bench.npz"
  sshpass -p "$BOARD_PASS" ssh "${ssh_opts[@]}" "root@${BOARD_IP}" \
    "cd /tmp/edgeai_bench && timeout 45 ${env} N_BENCH=1 N_STREAM=1 N_ACCURACY=1 RUN_CPU=0 python3 board_latency_compare.py"
  # N=1000 at the current 57 ms/frame does not fit in the 45s devmem guard.
  # After A1' the same command is seconds; 600s is the measurement budget, not a scan tool.
  sshpass -p "$BOARD_PASS" ssh "${ssh_opts[@]}" "root@${BOARD_IP}" \
    "cd /tmp/edgeai_bench && timeout 600 ${env} N_BENCH=1000 N_STREAM=1000 N_ACCURACY=1000 RUN_CPU=0 \
      SAVE_PREDS=/tmp/edgeai_bench/correct_board.npy \
      OUT_JSON=/tmp/edgeai_bench/fpga_latency_compare.json \
      python3 board_latency_compare.py"
  sshpass -p "$BOARD_PASS" scp "${ssh_opts[@]}" \
    "root@${BOARD_IP}:/tmp/edgeai_bench/fpga_latency_compare.json" \
    "${REPO}/results/opt_v2/${VARIANT}_fpga_latency_compare.json"
  sshpass -p "$BOARD_PASS" scp "${ssh_opts[@]}" \
    "root@${BOARD_IP}:/tmp/edgeai_bench/correct_board.npy" \
    "${REPO}/results/opt_v2/correct_${VARIANT}_board_raw.npy" || true
}

stage_record() {
  conda activate edgeai_39
  local lat="${REPO}/results/opt_v2/${VARIANT}_fpga_latency_compare.json"
  local extra=()
  if [[ -f "$lat" ]]; then
    extra+=(--latency-json "$lat")
  fi
  python3 scripts/opt_v2/experiment_record.py --variant "$VARIANT" --notes "${NOTES:-}" "${extra[@]}"
  conda deactivate || true
}

log "repo=$REPO stage=$STAGE"
case "$STAGE" in
  convert) stage_convert ;;
  patch) stage_patch ;;
  csim) stage_csim ;;
  csynth) stage_csynth ;;
  impl) stage_impl ;;
  deploy) stage_deploy ;;
  record) stage_record ;;
  hls)
    stage_convert
    stage_patch
    stage_csynth
    ;;
  all)
    stage_convert
    stage_patch
    stage_csim
    stage_csynth
    stage_impl
    stage_deploy
    stage_record
    ;;
  *)
    echo "unknown STAGE=$STAGE" >&2
    exit 1
    ;;
esac
log "done"
