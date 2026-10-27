#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
H=${EDGEAI_ROOT}
echo "---- tb dat ----"
ls -lh "$H/notebooks/hls4ml_prj/tb_data/tb_input_features.dat" 2>/dev/null || echo no_dat
echo "---- prepare rss ----"
ps -p 84 -o etime,pcpu,rss,cmd
echo "---- ssh io ----"
# the ssh child; find it
ps -ef | grep 'ssh -o ConnectTimeout' | grep -v grep
SP=$(ps -ef | awk '/ssh -o ConnectTimeout/ && !/awk/ {print $2; exit}')
echo "ssh pid $SP"
if [ -n "$SP" ]; then
  tr '\0' ' ' < /proc/$SP/cmdline; echo
  echo "state $(awk '/State/ {print $2,$3}' /proc/$SP/status)"
  awk '/rchar|wchar|read_bytes|write_bytes/ {print}' /proc/$SP/io 2>/dev/null || true
fi
echo "---- log bytes ----"
wc -c "$H/results/opt_v2/logs/v4_board_10k.log"
date
