#!/bin/bash
# Fail early if WSL RAM is too small for Vivado HLS on this design.
set -euo pipefail

MIN_GB="${WSL_MIN_MEM_GB:-24}"
MEM_KB=$(awk '/^MemTotal:/{print $2}' /proc/meminfo)
SWAP_KB=$(awk '/^SwapTotal:/{print $2}' /proc/meminfo)
MEM_GB=$((MEM_KB / 1024 / 1024))
SWAP_GB=$((SWAP_KB / 1024 / 1024))

echo "WSL Mem=${MEM_GB}G Swap=${SWAP_GB}G (min recommended Mem>=${MIN_GB}G)"

if [ "$MEM_GB" -lt "$MIN_GB" ] && [ "${FORCE_LOW_MEM:-0}" != "1" ]; then
  echo "ERROR: WSL memory ${MEM_GB}G < ${MIN_GB}G — v9 OOM likely at ~14GB HLS peak." >&2
  echo "Fix: set .wslconfig memory=32GB, then: wsl --shutdown" >&2
  echo "Or rerun with FORCE_LOW_MEM=1 (not recommended)." >&2
  exit 1
fi
