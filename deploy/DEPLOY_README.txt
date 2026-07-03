EdgeAI-ZU4EV 部署包说明
========================
工具：Vivado 2020.1
更新：2026-07-03（serial GAP / 板端 DRAM 对齐调试版）

文件清单
--------
  cifar10_accel.bit   — FPGA 比特流（经 fpga_manager 或 FSBL 加载）
  cifar10_accel.hwh   — 硬件移交文件（地址映射 / IP 参数）
  cifar10_accel.xsa   — Xilinx 支持归档（PetaLinux BSP 输入）
  cifar10_accel.ltx   — ILA 探针定义（可选，Hardware Manager 调试）
  dense_head.npz      — PS 侧 Dense 权重（板端 Top-1 必需）
  cifar10_bench.npz   — 板端 benchmark 数据集（默认不纳入 Git，需本地生成）

当前推荐 bit（2026-07-03）
--------------------------
  MD5 (bit): e64130011ab039a86a8347b320b565a7
  MD5 (hwh): af03c6b930d424a7a95fe9e076ce67bd

  特性：HLS 32-bit serial 输出直连 DMA S2MM；无 axis_dw_s2mm；
        DMA M_AXI 32-bit，S2MM DRE 已启用；数据路径经 HP0_FPD。

板端部署（PetaLinux + devmem，不用 PYNQ Overlay）
------------------------------------------------
  1. 板子启动 PetaLinux 2020.1，确认 SSH 可达（设置 BOARD_IP）

  2. 从开发机拷贝 bit 与脚本到板子（在仓库根目录执行）：
       export BOARD_IP=<your-board-ip>
       scp deploy/cifar10_accel.bit root@${BOARD_IP}:/lib/firmware/
       scp scripts/board_load_only.sh scripts/dma_infer_common.py \
           scripts/board_fetch_gap.py root@${BOARD_IP}:/tmp/edgeai_bench/

  3. 加载 PL（必须先于任何 /dev/mem 或 DMA 访问）：
       ssh root@${BOARD_IP}
       cp /tmp/edgeai_bench/cifar10_accel.bit /lib/firmware/
       FORCE_PL_RELOAD=1 sh /tmp/edgeai_bench/board_load_only.sh
       cat /sys/class/fpga_manager/fpga0/state    # 应为 operating

  4. 板端环境变量（serial GAP，24 维）：
       OUT_DIM=24 OUT_BYTES=96 OUT_LAYOUT=gap_ps
       OUT_FIXED_SCALE=1024 OUTPUT_PACK_MODE=serial

  5. 安全验收（单次 fetch，不跑 N=100 扫描）：
       bash scripts/board_safe_verify.sh          # 在 WSL 侧执行

  6. 0xAA 预填诊断（判定 DRAM 洞布局）：
       OUT_DIM=24 OUT_BYTES=96 OUTPUT_PACK_MODE=serial PREFILL_BYTES=96 \
         python3 board_aa_serial96_diag.py

已知问题与下一步
----------------
  - ILA 已证实 HLS 输出 24 拍 serial 正确。
  - DRAM 读回仍为「12 数据 + 12 洞」稀疏布局（32b DMA vs 64b HP0）。
  - 软件层已提供 hole-pair 解码与 HP0 devmem 补丁，N=100 Top-1 约 26%。
  - 根治方案：在 psu_init / BOOT.BIN 中固化 HP0 32-bit（AR66295），SD 启动。

  详见：results/board_s2mm_freshness_diag.json

PetaLinux BSP 重建（可选）
--------------------------
  petalinux-create -t project -n edgeai_bsp
  petalinux-config --get-hw-description=cifar10_accel.xsa
  petalinux-build
  petalinux-package --boot --u-boot --fpga cifar10_accel.bit --force

注意
----
  - bit / hwh / xsa 必须同一次 Vivado 导出，部署前核对 MD5 与时间戳。
  - 禁止在 fpga0 非 operating 时访问 CMA（0x66C00000）或 DMA（0x80040000）。
  - 禁止 ILA armed 时执行 board_load_only 重载。
