#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
H=${EDGEAI_ROOT}
echo "==== last result line ===="
tail -n 1 "$H/notebooks/hls4ml_prj/tb_data/csim_results.log" | awk '{print NF, length($0)}'
echo "==== dat lines ===="
wc -l "$H/notebooks/hls4ml_prj/tb_data/tb_input_features.dat"
echo "==== csim.exe ===="
find "$H/notebooks/hls4ml_prj/myproject_prj/solution1/csim" -name 'csim.exe' -o -name 'myproject_axi' 2>/dev/null | head
ls -lh "$H/notebooks/hls4ml_prj/myproject_prj/solution1/csim/build/csim.exe" 2>/dev/null || echo no_exe
echo "==== csim script end ===="
# skip the warning flood; show non-warning tail markers
grep -E 'ERROR|DONE|csim failed|Wrote|=== ' "$H/results/opt_v2/logs/v4_csim_10k.log" | tail -n 20
echo "==== dmesg-ish: file mtime ===="
stat -c '%y %s %n' "$H/notebooks/hls4ml_prj/tb_data/csim_results.log"
