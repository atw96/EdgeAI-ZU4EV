#!/bin/bash
# One-shot ILA bit+ltx build (System ILA output_stream + native reset ILA)
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
LOG="$REPO/results/ila_final_build.log"
cd "$REPO"
mkdir -p results
: >"$LOG"
exec >"$LOG" 2>&1
echo "[$(date '+%F %T')] === ila_final_build start ==="
source /tools/Xilinx/Vivado/2020.1/settings64.sh
export HLS_OUTPUT_AXIS_BITS=32
echo "--- create_block_design.tcl (32-bit HLS out, 64-bit DMA M_AXI + DRE) ---"
vivado -mode batch -source tcl/create_block_design.tcl
if grep -q axis_dw_s2mm vivado_project/EdgeAI_ZU4EV.srcs/sources_1/bd/system/system.bd 2>/dev/null; then
  echo "ERROR: axis_dw_s2mm still present after BD rebuild" >&2
  exit 1
fi
echo "INFO: BD OK — no axis_dw_s2mm"
echo "--- add_dma_ila.tcl ---"
vivado -mode batch -source tcl/add_dma_ila.tcl
echo "--- FORCE_REBUILD impl ---"
FORCE_REBUILD=1 vivado -mode batch -source tcl/run_impl_and_bitstream.tcl
if [ ! -f deploy/cifar10_accel.ltx ]; then
  echo "--- write_debug_probes fallback ---"
  vivado -mode batch <<'EOF'
open_project vivado_project/EdgeAI_ZU4EV.xpr
open_run impl_1
write_debug_probes -force -file deploy/cifar10_accel.ltx
exit
EOF
fi
echo "--- artifacts ---"
ls -la deploy/cifar10_accel.bit deploy/cifar10_accel.ltx
md5sum deploy/cifar10_accel.bit deploy/cifar10_accel.ltx
stat -c '%y %n' deploy/cifar10_accel.bit deploy/cifar10_accel.ltx
echo "[$(date '+%F %T')] === ila_final_build DONE ==="
