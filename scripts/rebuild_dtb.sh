#!/bin/bash
# Rebuild only device-tree and repackage image.ub
LOG=/home/atw/petalinux_projects/axu4ev_factory_dtb_rebuild.log
exec > "$LOG" 2>&1
echo "=== DTB REBUILD START $(date) ==="

source /opt/pkg/petalinux/2020.1/settings.sh
cd /home/atw/petalinux_projects/axu4ev_factory

echo "=== building device-tree $(date) ==="
petalinux-build -c device-tree
echo "=== device-tree build exit=$? $(date) ==="

echo "=== building full image $(date) ==="
petalinux-build
echo "=== petalinux-build exit=$? $(date) ==="

echo "=== packaging $(date) ==="
petalinux-package --boot \
    --fsbl images/linux/zynqmp_fsbl.elf \
    --pmufw images/linux/pmufw.elf \
    --atf images/linux/bl31.elf \
    --u-boot images/linux/u-boot.elf \
    --force

echo "=== updating sd_card_staging $(date) ==="
mkdir -p sd_card_staging
cp images/linux/BOOT.BIN images/linux/image.ub images/linux/boot.scr sd_card_staging/
echo "=== Files in sd_card_staging: ==="
ls -lh sd_card_staging/

echo "=== DONE $(date) ==="
