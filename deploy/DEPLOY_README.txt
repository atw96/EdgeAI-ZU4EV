EdgeAI-ZU4EV 部署包说明
========================
工具：Vivado / Vitis HLS / PetaLinux 2020.1
更新：2026-10-27（RC2，GAP 在 PL，Dense 在 PS）

文件
----
  cifar10_accel.bit   — FPGA bitstream。Git 不收录，本地构建或从发布包取得。
  cifar10_accel.hwh   — 硬件移交（地址映射）
  cifar10_accel.xsa   — PetaLinux 用的硬件描述
  dense_head.npz      — PS 侧 Dense 24→10

本地三份 bitstream 不要互相覆盖：

  已知良好版   MD5 46987907f8177883048b705fdf68c370
  RC1          MD5 334e27454dcb05d179d6d188b7d404c3
  RC2（推荐）  MD5 395160123c39a98d478e598c9f93e39e

RC2 的复用因子是 27/36/144/90/180/216。DMA 为 Simple 模式，M_AXI 64-bit。
HLS 输出 24 个 int16（96 字节，serial）直连 S2MM。

板端
----
  1. 设置 BOARD_IP。不要把具体地址写进仓库。

  2. 拷贝 RC2 的 bit、hwh 和 dense_head.npz 到板上的工作目录。

  3. 若要跑推荐点：把 PL0_REF_CTRL 的 DIVISOR0 写成 10（DIVISOR1 保持 1），
     立刻用 fpga_manager 重新加载这份 bit，读回应为 0x01010a02
     （149.9136 MHz）。上电默认是 DIVISOR0=15（99.9424 MHz）。
     不要在 fabric 已经加载并正在运行时写这个寄存器。

  4. 加载：
       FORCE_PL_RELOAD=1 sh board_load_only.sh
       cat /sys/class/fpga_manager/fpga0/state     # operating
     该脚本会把 HP0 的 AFIFM 设为 64-bit。不做这一步，S2MM 会写成稀疏洞。

  5. 推理进程的环境：
       OUT_DIM=24 OUT_BYTES=96 OUT_LAYOUT=gap_ps
       OUT_FIXED_SCALE=1024 OUTPUT_PACK_MODE=serial

  6. fpga0 不是 operating 时，不要访问 DMA 或输入输出缓冲。

计时口径
--------
  C 热路径在启动前把 S2MM/MM2S 的 IOC 清掉并读回为 0。
  RC2 @ 149.9136 MHz：T_wait 0.384 ms，T_hot 0.397 ms（1 万张）。
  Python 路径若只清 IOC、不读回，149.9 MHz 上尾部 32 字节可能停在 0xAA 并锁住。

注意
----
  bit 与 hwh 必须来自同一次实现。部署前核对 MD5。
  5 ns 是签核约束。板上运行点是 149.9 MHz，不要把两套数字写成同一个 WNS。
