# EdgeAI-ZU4EV：Zynq UltraScale+ 实时 CNN 推理加速器

[![Vivado](https://img.shields.io/badge/Vivado-2020.1-blue?logo=xilinx)](https://www.xilinx.com/products/design-tools/vivado.html)
[![PetaLinux](https://img.shields.io/badge/PetaLinux-2020.1-blue?logo=linux)](https://www.xilinx.com/products/design-tools/embedded-software/petalinux-sdk.html)
[![hls4ml](https://img.shields.io/badge/hls4ml-1.3-green)](https://fastmachinelearning.org/hls4ml/)
[![Python](https://img.shields.io/badge/Python-3.9+-yellow)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-lightgrey)](LICENSE)

**端到端链路：** QKeras Q6 量化 → hls4ml 1.3（GAP 在 PL，Dense 在 PS）→ Vivado Block Design → PetaLinux（fpga_manager + devmem / AXI-DMA，**不用 PYNQ Overlay**）

---

## 项目概述

在 **ALINX ACU4EV**（Xilinx Zynq UltraScale+ XCZU4EV）上实现 CIFAR-10 学生网络加速器。通道数为 16/16/20/20/24/24。PL 只做卷积和全局平均池化，输出 24 维 GAP；PS 用一份小的 Dense 头（24→10）得到类别。

当前推荐比特流是 **RC2**（A2-L 复用因子）。已知良好版和 RC1 仍保留在本地 `deploy/`，本仓库不收录 bitstream。

---

## 当前状态（2026-10-27）

运行点：`PL0_REF_CTRL` 的 `DIVISOR0=10`、`DIVISOR1=1`，读回字 `0x01010a02`，PL 时钟 **149.9136 MHz**。上电后寄存器会回到 `DIVISOR0=15`（99.9424 MHz）。改分频必须先写寄存器、立刻重新加载同一份 bitstream，不能在 fabric 正在跑的时候写这个寄存器。

### 功能与面积

| 指标 | 结果 |
|------|------|
| 板端 / csim Top-1 | **81.78%**（同一份 1 万张；Keras 81.90%） |
| 1 万张自然图像 GAP | 板端与 csim 逐比特一致 |
| 729 张合成图像 | A2-L csim、RC1 csim、板端三者最大差 0 LSB |
| 布线后 LUT as Logic | 44 692 / 87 840 |
| DSP48E2 | 207 / 728 |
| BRAM tile | 25 |
| 5 ns 约束 WNS | +0.048 ns（Performance_Explore；不是每种策略都过） |

### 延迟（C 热路径，1 万张 × 3）

`T_wait` 是启动 DMA 之后等到 S2MM 完成。`T_hot` 含写输入、启动、等待、读回、解码和 Dense。

| 设计 | 时钟 | `T_wait` | `T_hot` |
|------|------|----------|---------|
| 旧 bitstream | 99.94 MHz | 57.11 ms | 57.12 ms |
| RC1 | 99.94 MHz | 1.684 ms | 1.698 ms |
| RC1 | 149.9 MHz | 1.123 ms | 1.137 ms |
| **RC2** | 99.94 MHz | 0.576 ms | 0.590 ms |
| **RC2** | **149.9 MHz** | **0.384 ms** | **0.397 ms** |

同时钟下，旧 bitstream 到 RC2 的等待时间是 **99.2 倍**。RC2 跑在 149.9 MHz 时，相对旧 bitstream 是 **148.7 倍**。RC2 单流大约 2 518 FPS。

C 热路径在 99.94 MHz 与 149.9 MHz 上的长跑都是 0 次尾部哨兵。RC2 在 149.9 MHz 上 1 000 万帧 0 事件，Garwood 95% 上界 0.37 次/百万帧。

### 与 A53 上 TFLite INT8 的对照

同一份 1 万张、同一顺序。CPU 模型不是 FPGA 这条网络。

| 口径 | 1 线程 | 4 线程 |
|------|--------|--------|
| Top-1 | 79.33% | 79.33% |
| 只计 `invoke` | 13.86 ms | 12.18 ms |
| 端到端（负载到类别） | 14.03 ms | 12.38 ms |

RC2 的 `T_hot` 0.397 ms 相对 1 线程端到端约 35 倍，相对 4 线程约 31 倍。

功耗没有板外功率计，不在这里给 J/帧。片上温度传感器在一次 70 分钟连续推理前后读到 PL 约 35 °C。

---

## 架构

```
uint8 图像
  → PS：量化为 int16，scale 1024，6144 字节
  → AXI DMA MM2S
  → PL：myproject_axi（卷积 + GAP，24×int16，96 字节，serial）
  → AXI DMA S2MM
  → PS：Dense 24→10
```

| 项 | 值 |
|----|----|
| HLS 顶层 | `myproject_axi` |
| BD / IP | `system` / `cifar10_accel` |
| DMA | Simple 模式，M_AXI 64-bit，DRE 关闭 |
| HP0 | 加载后把 AFIFM 设为 64-bit（AR66295） |
| 输出布局 | `OUT_LAYOUT=gap_ps`，`OUTPUT_PACK_MODE=serial` |
| RC2 复用因子 | 27 / 36 / 144 / 90 / 180 / 216 |

加载 bitstream 之后，HP0 经常仍是 32-bit。`scripts/board_load_only.sh` 会调用 `scripts/board_fix_hp0_width.py` 把它改成 64-bit。这一步不做，S2MM 会写成稀疏的洞。

Python 旧路径在 149.9 MHz 上会把完成标志清掉但不读回，尾部 32 字节可能一直停在预先写入的 `0xAA`，并且一旦发生会锁住很多帧。C 热路径在启动前把 IOC 读回为 0。沿用 Python 路径时要做同样的读回。

---

## 硬件平台

| 资源 | 规格 |
|------|------|
| **SoC** | Xilinx Zynq UltraScale+ XCZU4EV-1SFVC784I |
| **LUT** | 87 840 |
| **DSP48E2** | 728 |
| **BRAM** | 256 × BRAM_18K |
| **PS DDR4** | 4 GB，64-bit |
| **PS CPU** | ARM Cortex-A53 四核 |
| **工具链** | Vivado / Vitis HLS 2020.1，PetaLinux 2020.1 |

---

## 环境

| 用途 | 说明 |
|------|------|
| 工程根目录 | 克隆仓库后的根目录 |
| 板子地址 | 环境变量 `BOARD_IP`（局域网 DHCP） |
| 板上工作目录 | `/tmp/edgeai_bench/` |

工具链和 Conda 环境按本机安装路径自行 `source` / 激活。不要把个人主目录写进脚本后提交。

本地三份 bitstream 的 MD5（文件不在 Git 里）：

| 角色 | MD5 |
|------|-----|
| 已知良好版 `deploy/cifar10_accel.bit` | `46987907f8177883048b705fdf68c370` |
| RC1 | `334e27454dcb05d179d6d188b7d404c3` |
| **RC2（推荐）** | `395160123c39a98d478e598c9f93e39e` |

---

## 板端推理

`fpga0` 不是 `operating` 时，不要访问 DMA 或输入输出缓冲。未加载 PL 就读这些地址会把 AXI 总线挂死。

```bash
export BOARD_IP=<your-board-ip>

# 只加载 PL，并在加载后把 HP0 设为 64-bit
FORCE_PL_RELOAD=1 sh scripts/board_load_only.sh

# 单次验收
bash scripts/board_safe_verify.sh
```

板端进程使用：

```bash
OUT_DIM=24 OUT_BYTES=96 OUT_LAYOUT=gap_ps \
  OUT_FIXED_SCALE=1024 OUTPUT_PACK_MODE=serial
```

推荐运行点还要把 `DIVISOR0` 写成 10，然后立刻重新加载 RC2，并读回 `0x01010a02`。读回不是这个字就不要开始计时。

默认不要跑全量扫描或上百次重复基准；那些脚本会长时间占用 DMA。

---

## Vivado / HLS

在仓库根目录执行，并先 `source` 对应的 2020.1 settings 脚本。

```bash
# Block Design：DMA M_AXI 64-bit，HLS 输出直连 S2MM
vivado -mode batch -source tcl/create_block_design.tcl

# 综合、实现、bitstream
vivado -mode batch -source tcl/run_impl_and_bitstream.tcl
```

签核约束是 5 ns。板上实际用 149.9 MHz（周期约 6.67 ns）。不要把约束改成 6.67 ns 再拿那个 bitstream 当 5 ns 的签核结果。

---

## 工程目录

```
EdgeAI-ZU4EV_Claude/
├── notebooks/          # 训练、量化、HLS 工程
├── scripts/            # 转换、板端、构建脚本
├── tcl/                # Vivado Block Design 与实现
├── constraints/        # XDC
├── deploy/             # 本地 bitstream 与 Dense 权重（大文件不入库）
├── results/            # 测量记录
├── docs/               # 设计说明
└── README.md
```

---

## 参考资料

1. [hls4ml](https://fastmachinelearning.org/hls4ml/) — Duarte et al., JINST 13 (2018)
2. [QKeras](https://github.com/google/qkeras) — Coelho et al., Nature Electronics (2021)
3. [Zynq UltraScale+ TRM](https://docs.xilinx.com/r/en-US/ug1085-zynq-ultrascale-trm)（UG1085）
4. [Zynq UltraScale+ 寄存器参考](https://docs.amd.com/r/en-US/ug1087-zynq-ultrascale-registers)（UG1087，`PL0_REF_CTRL`）
5. [AXI DMA PG021](https://docs.xilinx.com/r/en-US/pg021-axi-dma)
6. AMD AR66295 — PS-PL AXI 位宽

---

## 许可证

MIT License — 见 [LICENSE](LICENSE)。
