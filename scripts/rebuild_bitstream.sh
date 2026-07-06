#!/bin/bash
# Rebuild Vivado project with fixed clock domain (all DMA on pl_clk0)
# Usage: bash rebuild_bitstream.sh [--no-sync]
set -e

REPO_WSL="/home/atw/Edge_AI_Acc/claude/EdgeAI-ZU4EV_Claude"
REPO_WIN="/mnt/e/WSL_ENV/project/EdgeAI-ZU4EV_Claude"

# Sync key files from Windows to WSL
if [[ "$1" != "--no-sync" ]]; then
    echo "[1/4] Syncing TCL scripts from Windows path..."
    cp -v "${REPO_WIN}/tcl/create_block_design.tcl"   "${REPO_WSL}/tcl/"
    cp -v "${REPO_WIN}/tcl/run_impl_and_bitstream.tcl" "${REPO_WSL}/tcl/"
    cp -v "${REPO_WIN}/tcl/export_bitstream.tcl"      "${REPO_WSL}/tcl/" 2>/dev/null || true
fi

# Source Vivado environment
echo "[2/4] Sourcing Vivado 2020.1 environment..."
source /tools/Xilinx/Vivado/2020.1/settings64.sh

cd "${REPO_WSL}"

# Clear stale IP cache when forcing rebuild
if [[ "${FORCE_REBUILD:-0}" == "1" ]]; then
    echo "[3/4] FORCE_REBUILD=1 — clearing vivado_project/.cache/ip"
    rm -rf "${REPO_WSL}/vivado_project/.cache/ip" 2>/dev/null || true
fi

# Stage 1: Recreate block design (fresh project)
echo "[3/4] Creating block design (forces fresh project)..."
vivado -mode batch -nojournal -nolog \
       -source tcl/create_block_design.tcl \
       2>&1 | tee bd_create.log
if [[ ! -f vivado_project/EdgeAI_ZU4EV.xpr ]]; then
    echo "ERROR: Project not created. See bd_create.log"
    exit 1
fi

# Stage 2: Run synthesis + implementation + bitstream
echo "[4/4] Running synth + impl + bitstream (this takes ~45-60 minutes)..."
FORCE_REBUILD="${FORCE_REBUILD:-0}" vivado -mode batch -nojournal -nolog \
       -source tcl/run_impl_and_bitstream.tcl \
       2>&1 | tee impl_build.log
IMPL_RC=${PIPESTATUS[0]}

# Verify outputs
if [[ $IMPL_RC -eq 0 && -f deploy/cifar10_accel.bit && -f deploy/cifar10_accel.hwh ]]; then
    echo
    echo "================================================================"
    echo " BUILD SUCCESS"
    echo "   $(ls -la deploy/cifar10_accel.bit)"
    echo "   $(ls -la deploy/cifar10_accel.hwh)"
    echo "================================================================"
    # Copy back to Windows path for easy access
    cp -v deploy/cifar10_accel.bit "${REPO_WIN}/deploy/"
    cp -v deploy/cifar10_accel.hwh "${REPO_WIN}/deploy/"
else
    echo "ERROR: Vivado build failed (rc=${IMPL_RC}) or deploy/cifar10_accel.{bit,hwh} missing - check impl_build.log"
    ls -la deploy/ 2>/dev/null || true
    exit 1
fi
