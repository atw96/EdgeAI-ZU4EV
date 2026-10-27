#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
# X5 A2-L. Waits until the X4 multi-strategy Vivado batch has released the project.
# Converts into a side tree, keeps the RC1 HLS project, writes the bit under results/opt_v2/a2l/.
# Does not replace deploy/cifar10_accel.bit or deploy/opt_v2/A1shallow/.
set -euo pipefail
H=${EDGEAI_ROOT}
M=${EDGEAI_ROOT}
LOG=$H/results/opt_v2/logs/v8_x5_a2l.log
mkdir -p "$H/results/opt_v2/logs" "$H/results/opt_v2/a2l"
exec > >(tee -a "$LOG") 2>&1
echo "[$(date '+%F %T')] wait for x4 vivado"
while pgrep -f 'x4_multiseed.tcl' >/dev/null; do
  sleep 20
done
echo "[$(date '+%F %T')] x5 A2-L convert"
cd "$H"
restore_hls() {
  if [ -d notebooks/hls4ml_prj.bak_bitexact_before_a2l ] && [ ! -d notebooks/hls4ml_prj_a2l ]; then
    if [ -d notebooks/hls4ml_prj ]; then
      mv notebooks/hls4ml_prj notebooks/hls4ml_prj_a2l
    fi
    mv notebooks/hls4ml_prj.bak_bitexact_before_a2l notebooks/hls4ml_prj
  fi
  if [ -f /tmp/v19_rf_a1.py ]; then
    cp -a /tmp/v19_rf_a1.py scripts/v19_hls_config_common.py || true
  fi
}
trap restore_hls EXIT
cp -a scripts/v19_hls_config_common.py /tmp/v19_rf_a1.py
cp -f "$M/scripts/opt_v2/set_rf.py" scripts/opt_v2/set_rf.py || true
source ${HOME}/miniconda3/etc/profile.d/conda.sh
conda activate edgeai_hls4ml13
export PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python
export BIT_EXACT=0 GAP_ONLY=1 BAK_TAG=before_a2l OPT_V2_KEEP_RF=1
python3 scripts/opt_v2/set_rf.py --variant A2-L
python3 -u scripts/v19_bitexact_convert.py
echo "[$(date '+%F %T')] patches"
conda activate edgeai_39
python3 scripts/patch_hls_rf_v14.py
python3 scripts/patch_hls_restore_dataflow.py
python3 scripts/patch_hls_conv_stream.py || true
python3 scripts/patch_hls_stream_depth.py
python3 scripts/patch_hls_dense_mult.py
python3 scripts/patch_hls_axi_top.py || true
python3 scripts/patch_axi_wrapper.py
python3 scripts/patch_axi_testbench.py
if ! grep -n "DATAFLOW" notebooks/hls4ml_prj/firmware/myproject.cpp >/dev/null; then
  echo "NO_DATAFLOW"
  exit 4
fi
echo "[$(date '+%F %T')] csim 1000"
export SKIP_BOARD=1 N_GAP_COMPARE=1000
bash scripts/run_gap_axi_csim.sh
cp -f notebooks/hls4ml_prj/tb_data/csim_results.log results/opt_v2/a2l/csim_results.log
python3 scripts/opt_v2/bitexact_gap_compare.py \
  results/opt_v2/a1_shallow_csim.log \
  results/opt_v2/a2l/csim_results.log --n 1000
echo "[$(date '+%F %T')] csynth"
source /tools/Xilinx/Vivado/2020.1/settings64.sh
cd notebooks/hls4ml_prj
rm -rf myproject_prj/solution1/.autopilot myproject_prj/solution1/syn
/tools/Xilinx/Vivado/2020.1/bin/vivado_hls -f build_prj.tcl reset=1 csim=0 synth=1 cosim=0 validation=0 export=1
cd "$H"
python3 - <<'PY'
import json, re
from pathlib import Path
repo = Path(__import__("os").environ["EDGEAI_ROOT"])
rpt = repo / "notebooks/hls4ml_prj/myproject_prj/solution1/syn/report/myproject_axi_csynth.rpt"
text = rpt.read_text(errors="replace")
lines = text.splitlines()
lat = None
for i, line in enumerate(lines):
    if "Latency (cycles)" not in line:
        continue
    for nxt in lines[i+1:i+8]:
        cells = [c.strip() for c in nxt.strip().strip("|").split("|")]
        nums = [int(c.replace(",", "")) for c in cells if re.fullmatch(r"[\d,]+", c)]
        if len(nums) >= 2:
            lat = nums[1]
            break
    if lat:
        break
util = {}
for line in lines:
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    if cells and cells[0] == "Total" and len(cells) >= 6:
        for k, c in zip(("BRAM_18K", "DSP48E", "FF", "LUT"), cells[1:5]):
            if re.fullmatch(r"[\d,]+", c):
                util[k] = int(c.replace(",", ""))
        break
out = {"top_latency_cycles_max": lat, "util": util, "bound_cycles": 64758}
path = repo / "results/opt_v2/a2l/csynth.json"
path.write_text(json.dumps(out, indent=2) + "\n")
print(json.dumps(out))
red = []
if util.get("LUT", 0) >= 60000:
    red.append("LUT")
if util.get("DSP48E", 0) >= 500:
    red.append("DSP")
if util.get("BRAM_18K", 0) >= 160:
    red.append("BRAM")
if red:
    raise SystemExit("AREA_RED " + ",".join(red))
PY
echo "[$(date '+%F %T')] park A2-L tree and restore RC1 HLS project"
if [ -d notebooks/hls4ml_prj_a2l ]; then
  rm -rf notebooks/hls4ml_prj_a2l
fi
mv notebooks/hls4ml_prj notebooks/hls4ml_prj_a2l
mv notebooks/hls4ml_prj.bak_bitexact_before_a2l notebooks/hls4ml_prj
cp -a /tmp/v19_rf_a1.py scripts/v19_hls_config_common.py
echo "[$(date '+%F %T')] impl copy"
rm -rf vivado_project_a2l
cp -a vivado_project vivado_project_a2l
cat > /tmp/x5_a2l_impl.tcl << 'EOF'
set proj $::env(EDGEAI_ROOT)/vivado_project_a2l/EdgeAI_ZU4EV.xpr
set iprepo $::env(EDGEAI_ROOT)/notebooks/hls4ml_prj_a2l/myproject_prj/solution1/impl/ip
set outdir $::env(EDGEAI_ROOT)/results/opt_v2/a2l
open_project $proj
set_property ip_repo_paths [list $iprepo] [current_project]
update_ip_catalog
set ips [get_ips *cifar*]
puts "IPS $ips"
upgrade_ip $ips
report_ip_status
if {[llength [get_runs synth_a2l]] == 0} {
  create_run synth_a2l -flow {Vivado Synthesis 2020}
}
if {[llength [get_runs impl_a2l]] == 0} {
  create_run impl_a2l -parent_run synth_a2l -flow {Vivado Implementation 2020} -strategy Performance_Explore
}
reset_run synth_a2l
launch_runs impl_a2l -to_step route_design -jobs 8
wait_on_run impl_a2l
set st [get_property STATUS [get_runs impl_a2l]]
set wns [get_property STATS.WNS [get_runs impl_a2l]]
set whs [get_property STATS.WHS [get_runs impl_a2l]]
puts "A2L_IMPL status $st WNS $wns WHS $whs"
if {$wns < 0} {
  close_project
  exit 5
}
open_run impl_a2l
write_bitstream -force [file join $outdir cifar10_accel.bit]
set hwh [glob -nocomplain vivado_project_a2l/*.srcs/sources_1/bd/system/hw_handoff/system.hwh]
if {[llength $hwh] > 0} {
  file copy -force [lindex $hwh 0] [file join $outdir cifar10_accel.hwh]
}
close_project
exit 0
EOF
cd "$H"
vivado -mode batch -source /tmp/x5_a2l_impl.tcl -log results/opt_v2/logs/x5_a2l_vivado.log -journal results/opt_v2/logs/x5_a2l.jou
echo "A2L_IMPL_RC $?"
