#!/bin/bash
# Add output_stream ILA probes, full synth+impl+bit+ltx export.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"
mkdir -p results

LOG="results/ila_output_rebuild.log"
mkdir -p results
exec >>"$LOG" 2>&1

echo "[$(date '+%F %T')] === run_ila_output_rebuild ==="
echo "REPO=$REPO"

# Stop any in-flight Vivado for this project
pkill -9 -f 'vivado.*EdgeAI_ZU4EV' 2>/dev/null || true
pkill -9 vivado 2>/dev/null || true
sleep 2
if pgrep -x vivado >/dev/null 2>&1; then
  echo "ERROR: vivado still running" >&2
  exit 1
fi
echo "INFO: vivado processes stopped"

source /tools/Xilinx/Vivado/2020.1/settings64.sh

echo "--- add_dma_ila.tcl (output_stream probes) ---"
vivado -mode batch -source tcl/add_dma_ila.tcl

echo "--- FORCE_REBUILD impl + bitstream + deploy export ---"
FORCE_REBUILD=1 vivado -mode batch -source tcl/run_impl_and_bitstream.tcl

echo "--- deploy artifact check ---"
ls -la deploy/cifar10_accel.bit deploy/cifar10_accel.ltx deploy/cifar10_accel.hwh 2>/dev/null || true
md5sum deploy/cifar10_accel.bit deploy/cifar10_accel.ltx 2>/dev/null || true
stat -c '%y %n' deploy/cifar10_accel.bit deploy/cifar10_accel.ltx 2>/dev/null || true

if [ ! -f deploy/cifar10_accel.ltx ]; then
  echo "WARN: no ltx after export — running write_debug_probes"
  vivado -mode batch <<'VIVADO_EOF'
open_project vivado_project/EdgeAI_ZU4EV.xpr
open_run impl_1
write_debug_probes -force -file deploy/cifar10_accel.ltx
exit
VIVADO_EOF
  ls -la deploy/cifar10_accel.ltx
  md5sum deploy/cifar10_accel.ltx
fi

BIT_SZ=$(stat -c%s deploy/cifar10_accel.bit 2>/dev/null || echo 0)
LTX_SZ=$(stat -c%s deploy/cifar10_accel.ltx 2>/dev/null || echo 0)
if [ "$LTX_SZ" -le 6000 ]; then
  echo "WARN: ltx size ${LTX_SZ} B looks like old stub (5582 B); verify ILA in bit"
fi

echo "[$(date '+%F %T')] === run_ila_output_rebuild DONE ==="
