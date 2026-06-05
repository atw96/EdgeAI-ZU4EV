#!/bin/bash
# Rebuild bitstream: reset-domain fix + optional loopback / bypass clk_wiz
set -euo pipefail

REPO_WSL="/home/atw/Edge_AI_Acc/claude/EdgeAI-ZU4EV_Claude"
REPO_WIN="/mnt/e/WSL_ENV/project/EdgeAI-ZU4EV_Claude"
BYPASS_CLK_WIZ="${BYPASS_CLK_WIZ:-0}"
DMA_STREAM_LOOPBACK="${DMA_STREAM_LOOPBACK:-1}"
LOG="${REPO_WSL}/rebuild_dma_fix.log"

log() { echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG"; }

log "=== DMA fix rebuild ==="
log "REPO_WSL=${REPO_WSL}"
log "BYPASS_CLK_WIZ=${BYPASS_CLK_WIZ} DMA_STREAM_LOOPBACK=${DMA_STREAM_LOOPBACK}"

log "=== Sync from Windows mount ==="
cp -v "${REPO_WIN}/tcl/create_block_design.tcl" "${REPO_WSL}/tcl/"
cp -v "${REPO_WIN}/tcl/run_impl_and_bitstream.tcl" "${REPO_WSL}/tcl/" 2>/dev/null || true
cp -v "${REPO_WIN}/scripts/rebuild_dma_fix.sh" "${REPO_WSL}/scripts/" 2>/dev/null || true

source /tools/Xilinx/Vivado/2020.1/settings64.sh
cd "${REPO_WSL}"

export BYPASS_CLK_WIZ DMA_STREAM_LOOPBACK
log "Phase 1: create_block_design"
vivado -mode batch -nojournal -nolog \
    -source tcl/create_block_design.tcl 2>&1 | tee -a "$LOG"

log "Phase 2: synth/impl/bit (FORCE_REBUILD=1)"
export FORCE_REBUILD=1
vivado -mode batch -nojournal -nolog \
    -source tcl/run_impl_and_bitstream.tcl 2>&1 | tee -a "$LOG"
unset FORCE_REBUILD

cp -v deploy/cifar10_accel.bit deploy/cifar10_accel.hwh "${REPO_WIN}/deploy/" 2>/dev/null || true
md5sum deploy/cifar10_accel.bit | tee -a "$LOG"
log "=== REBUILD DONE ==="

# Copy back to Windows deploy (for board_ssh_deploy.py)
if [ -d "${REPO_WIN}/deploy" ]; then
    cp -v deploy/cifar10_accel.bit deploy/cifar10_accel.hwh "${REPO_WIN}/deploy/" | tee -a "$LOG"
fi
