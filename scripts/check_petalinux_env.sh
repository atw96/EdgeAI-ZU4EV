#!/bin/bash
# EdgeAI-ZU4EV: check PetaLinux / XSA environment (run inside WSL)
set -u

PT_SETTINGS="/opt/pkg/petalinux/2020.1/settings.sh"
if [ -f "$PT_SETTINGS" ]; then
  # shellcheck disable=SC1090
  source "$PT_SETTINGS"
  PT_OK=1
else
  PT_OK=0
fi

echo "=== WSL ==="
uname -a

echo "=== PetaLinux ==="
echo "settings: $PT_SETTINGS"
if [ "$PT_OK" = 1 ]; then
  echo "sourced: yes"
  which petalinux-build petalinux-config petalinux-create petalinux-package
else
  echo "sourced: no — install or fix path to settings.sh"
fi

echo "=== XSA ==="
XSA="/home/atw/Edge_AI_Acc/claude/EdgeAI-ZU4EV_Claude/deploy/cifar10_accel.xsa"
if [ -f "$XSA" ]; then
  ls -lh "$XSA"
else
  echo "MISS: $XSA"
fi

echo "=== Disk ==="
df -h ~ | tail -1

echo "=== Verdict ==="
if [ "$PT_OK" = 1 ] && command -v petalinux-build >/dev/null 2>&1 && [ -f "$XSA" ]; then
  echo "READY for path-2: petalinux-create + get-hw-description from XSA"
else
  echo "NOT READY — see messages above"
fi
