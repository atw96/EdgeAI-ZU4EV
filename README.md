# EdgeAI-ZU4EV：Zynq UltraScale+ 实时 CNN 推理加速器

[![Vivado](https://img.shields.io/badge/Vivado-2020.1-blue?logo=xilinx)](https://www.xilinx.com/products/design-tools/vivado.html)
[![PetaLinux](https://img.shields.io/badge/PetaLinux-2020.1-blue?logo=linux)](https://www.xilinx.com/products/design-tools/embedded-software/petalinux-sdk.html)
[![hls4ml](https://img.shields.io/badge/hls4ml-1.3-green)](https://fastmachinelearning.org/hls4ml/)
[![Python](https://img.shields.io/badge/Python-3.9+-yellow)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-lightgrey)](LICENSE)

**端到端链路：** QKeras Q6 量化 → hls4ml 1.3 HLS（`bit_exact`）→ Vivado Block Design → PetaLinux 板端部署（devmem + AXI-DMA，**不用 PYNQ Overlay**）

---

## 项目概述

在 **ALINX ACU4EV**（Xilinx Zynq UltraScale+ XCZU4EV）上实现 CIFAR-10 轻量 CNN 加速器。模型经 QKeras 量化后，由 hls4ml 导出 **GAP-only PL IP**，PS 侧完成 Dense 头，经 Vivado 集成并在 PetaLinux 2020.1 上推理验证。

---

## 当前调试状态（2026-07-03）

### 仿真与模型（已达标，无需重训）

| 指标 | 结果 | 门槛 |
|------|------|------|
| HLS csim + PS Dense Top-1 | **82%** | ≥80% |
| GAP MAE | **0.026** | ≤0.35 |
| 门控文件 | `results/v19_route1_gates.json` | `overall_pass: true` |

### 板端（进行中：serial 输出 / DRAM 对齐）

| 指标 | 结果 | 目标 |
|------|------|------|
| ILA `output_stream` | **24 拍连续 serial**（HLS 出口正确） | — |
| DRAM `board_fetch_gap` | **12 数据字 + 12 洞**（稀疏布局） | 24 连续非零字 |
| N=100 Top-1 | **26%**（软件 hole 解码后；原 ~21%） | ~80%（对齐 csim） |
| DMA 延迟 | ~57 ms，IOC 正常 | — |

**根因（已锁定）：** 32-bit DMA M_AXI 经 64-bit SmartConnect / `S_AXI_HP0_FPD` 写入 DRAM，产生「2 数据 + 2 洞」布局；**非** HLS slot IP 或模型问题。

**PL 未放弃：** 推理仍在 `cifar10_accel_0`（HLS serial）上运行，bit 经 `fpga_manager` 加载。

**推荐下一步：** 在 `psu_init` / **BOOT.BIN（FSBL）** 中固化 HP0 32-bit 宽度（AMD AR66295），SD 启动后验收 AA 预填无洞。

详细诊断：`results/board_s2mm_freshness_diag.json`（B1：12 数据字 + 12 洞，HP0 位宽不匹配）

---

## 硬件平台

| 资源 | 规格 |
|------|------|
| **SoC** | Xilinx Zynq UltraScale+ XCZU4EV-1SFVC784I |
| **LUT** | 88,000 |
| **DSP48E2** | 728 |
| **BRAM** | 4.5 Mb（252 × BRAM_18K） |
| **PS DDR4** | 4 GB，64-bit |
| **PS CPU** | ARM Cortex-A53 四核 |
| **工具链** | Vivado / Vitis HLS 2020.1，PetaLinux 2020.1 |

---

## 环境与路径

| 用途 | 说明 |
|------|------|
| 工程根目录 | 克隆仓库后的根目录（下文命令均在此执行） |
| 板子 IP | 环境变量 `BOARD_IP`（局域网 DHCP，以实际为准） |
| 板上工作目录 | `/tmp/edgeai_bench/`（可自定义） |

**Conda 环境：** 按本地配置激活 QAT / 板端脚本环境与 hls4ml 1.3 转换环境。

---

## v19 Route 1 流水线（训练与 csim）

GAP-only 导出，`input_qact` 在 QAT 图中，`bit_exact=True`。

```bash
# 在仓库根目录 — QAT 微调 + bit_exact 转换 + csim 门控
FT_EPOCHS=40 CSIM_TOP1_MIN=75 N_ACCURACY=100 \
  bash scripts/run_v19_qat_resume.sh

cat results/v19_route1_gates.json
```

| 脚本 | 作用 |
|------|------|
| `scripts/run_v19_qat_resume.sh` | 主流程：微调 → 转换 → HLS 补丁 → csim → Top-1 门控 |
| `scripts/v19_bitexact_convert.py` | hls4ml 1.3 GAP-only 转换 |
| `scripts/v19_csim_route1_gates.py` | Top-1 主门控；MAE 辅助 |
| `scripts/setup_hls4ml13_env.sh` | hls4ml 1.3 环境安装 |

**导出布局（serial GAP）：** `OUT_DIM=24 OUT_BYTES=96 OUT_LAYOUT=gap_ps OUT_FIXED_SCALE=1024 OUTPUT_PACK_MODE=serial`

---

## 板端推理（devmem + DMA）

### 安全守则

- devmem / DMA 前确认 `fpga0 state=operating`
- 先 `FORCE_PL_RELOAD=1 sh board_load_only.sh` 再访问 CMA / DMA
- 统一用 **fpga_manager** 加载 bit（避免 JTAG 双源）
- 默认入口：`bash scripts/board_safe_verify.sh`

### 常用命令

```bash
# 部署 + 单次 fetch 验收（需先设置 BOARD_IP）
export BOARD_IP=<your-board-ip>
bash scripts/board_safe_verify.sh

# 板端环境变量（serial GAP）
OUT_DIM=24 OUT_BYTES=96 OUT_LAYOUT=gap_ps OUT_FIXED_SCALE=1024 OUTPUT_PACK_MODE=serial

# N=100 精度（需 dense_head.npz）
OUT_DIM=24 OUT_BYTES=96 OUT_LAYOUT=gap_ps OUT_FIXED_SCALE=1024 OUTPUT_PACK_MODE=serial \
  bash scripts/board_auto_fix.sh

# 0xAA 预填诊断（判定 DMA 洞布局）
OUT_DIM=24 OUT_BYTES=96 OUTPUT_PACK_MODE=serial PREFILL_BYTES=96 \
  python3 scripts/board_aa_serial96_diag.py
```

### 当前 deploy 产物（2026-07-03）

| 文件 | MD5 |
|------|-----|
| `deploy/cifar10_accel.bit` | `e64130011ab039a86a8347b320b565a7` |
| `deploy/cifar10_accel.hwh` | `af03c6b930d424a7a95fe9e076ce67bd` |
| `deploy/cifar10_accel.ltx` | `70142ec79f1cc9ab49e6e2fa260fd101` |

> 大体积 bit/xsa 默认不纳入 Git，请在本地 Vivado 构建后从 `deploy/` 取用。说明见 `deploy/DEPLOY_README.txt`。

### 板端关键脚本

| 脚本 | 作用 |
|------|------|
| `scripts/board_load_only.sh` | fpga_manager 加载 bit；加载后调用 HP0 宽度修复 |
| `scripts/board_fix_hp0_width.py` | AR66295：尝试将 HP0 设为 32-bit（fpga_manager 场景） |
| `scripts/dma_infer_common.py` | DMA/devmem 公共逻辑；自动 hole-pair DRAM 解码 |
| `scripts/board_fetch_gap.py` | 单次 DMA + GAP JSON 输出 |
| `scripts/board_aa_serial96_diag.py` | 0xAA 预填 + S2MM 洞布局诊断 |
| `scripts/ila_final_build.sh` | 一次性 bit + ltx 重建（含 BD 自检） |

---

## Vivado 构建

```bash
# 在仓库根目录
source /tools/Xilinx/Vivado/2020.1/settings64.sh

# Block Design（HLS 32-bit serial 输出）
export HLS_OUTPUT_AXIS_BITS=32
vivado -mode batch -source tcl/create_block_design.tcl

# 综合 + 实现 + bitstream
bash scripts/ila_final_build.sh
# 或：FORCE_REBUILD=1 vivado -mode batch -source tcl/run_impl_and_bitstream.tcl
```

**BD 要点：** HLS `output_stream` 直连 DMA S2MM（无 `axis_dw_s2mm`）；DMA M_AXI 32-bit + DRE；数据路径 DMA → SmartConnect → HP0_FPD。

---

## 工程目录

```
EdgeAI-ZU4EV_Claude/
├── notebooks/          # 训练 / 量化 / HLS notebook
├── scripts/            # Route1、板端、Vivado 构建脚本
├── tcl/                # Vivado Block Design / 实现 Tcl
├── constraints/        # 时序 XDC
├── deploy/             # bit / hwh / xsa / dense_head（大文件见 .gitignore）
├── results/            # 指标 JSON、交接文档、构建日志
├── docs/               # 设计说明与状态文档
└── README.md
```

---

## 性能参考（历史基线）

| 指标 | 数值 |
|------|------|
| FP32 测试精度 | 81.05% |
| Q6 QKeras（bench） | ~80–84% |
| PL LUT（全设计） | 24,702 / 88,000（28.07%） |

详见 `results/resource_report.md`。

---

## 参考资料

1. [hls4ml](https://fastmachinelearning.org/hls4ml/) — Duarte et al., JINST 13 (2018)
2. [QKeras](https://github.com/google/qkeras) — Coelho et al., Nature Electronics (2021)
3. [Zynq UltraScale+ TRM](https://docs.xilinx.com/r/en-US/ug1085-zynq-ultrascale-trm)（UG1085）
4. [AXI DMA PG021](https://docs.xilinx.com/r/en-US/pg021-axi-dma)
5. AMD AR66295 — PS-PL AXI 位宽与 `psu_init` 注意事项

---

## 许可证

MIT License — 见 [LICENSE](LICENSE)。
