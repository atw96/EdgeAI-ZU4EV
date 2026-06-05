# Claude Engineering Prompt: EdgeAI-ZU4EV Project

> **使用说明**：将以下 Prompt 完整复制粘贴给 Claude（claude.ai 或 API），要求其生成对应工程文件。建议按 Phase 分批发送，每次发送一个 Phase，避免单次输出过长。

---

## 全局背景（每次对话开始前附上）

```
我正在开发一个 FPGA AI 推理加速项目，用于作为求职 AI 硬件/芯片初创公司的作品集展示。

硬件平台：ALINX ACU4EV（Xilinx Zynq UltraScale+ XCZU4EV-1SFVC784I）
- LUT：88K
- DSP：728个（18×25）
- BRAM：4.5Mb
- PS DDR4：4GB 64bit
- PL DDR4：1GB 16bit
- VCU：H.264/H.265 硬件编解码单元
- PS：ARM Cortex-A53 四核 + Cortex-R5 双核
- 开发工具：Vivado 2022.2 / Vitis HLS 2022.2 / PetaLinux 2022.2

项目名称：EdgeAI-ZU4EV
目标：端到端 AI 推理加速演示，从模型量化 → HLS综合 → Block Design集成 → 板级部署
核心特色：利用板载 VCU 解码视频流，PL端 HLS 推理加速，AXI4-Stream 连接 PS-PL
我的背景：熟悉 Verilog RTL、AXI4协议、Zynq MPSoC 开发流程、hls4ml框架基础
```

---

## Phase 1 — 模型训练与量化（Python / Jupyter）

### Prompt 1A：CIFAR-10 紧凑模型训练

```
请生成一个完整的 Jupyter Notebook（cifar10_train.ipynb），要求：

任务：在 CIFAR-10 数据集上训练一个适合 FPGA 部署的紧凑 CNN 模型

模型架构要求（参数量 < 100K，适配 88K LUT 的 XCZU4EV）：
- Input: 32×32×3
- Conv2D(32, 3×3) + BatchNorm + ReLU
- MaxPool(2×2)
- Conv2D(64, 3×3) + BatchNorm + ReLU
- MaxPool(2×2)
- Conv2D(64, 3×3) + BatchNorm + ReLU
- GlobalAveragePooling
- Dense(10) + Softmax

训练要求：
- 使用 TensorFlow 2.x / Keras
- 数据增强：随机水平翻转、随机裁剪
- 优化器：Adam，lr=1e-3，余弦退火衰减
- 目标精度：> 80%
- 保存为 SavedModel 格式和 .h5 格式

输出内容：
1. 完整可运行的 Notebook 代码（含 markdown 说明）
2. 训练曲线绘图代码（accuracy/loss vs epoch）
3. 混淆矩阵绘图代码
4. 模型参数量统计代码
5. 最终输出：model_fp32.h5 和 saved_model/
```

### Prompt 1B：QKeras INT8 量化

```
基于 Prompt 1A 训练好的模型（model_fp32.h5），请生成 cifar10_quantize.ipynb：

任务：使用 QKeras 对模型进行量化，并对比不同量化精度

量化版本：
1. Float32 基线（直接加载 model_fp32.h5）
2. INT8 量化（QConv2D bits=8, kernel_quantizer='stochastic_ternary' 或 'quantized_bits(8,0,1)'）
3. INT4 量化（bits=4）

输出要求：
1. 完整 QKeras 量化代码（三个版本模型定义+训练fine-tune 5 epoch）
2. 精度对比表格（Float32 / INT8 / INT4 的 Test Accuracy）
3. 模型大小对比（.h5 文件大小）
4. 将 INT8 量化模型保存为 model_int8_qkeras.h5
5. 代码注释说明每个量化参数的含义

工具：pip install qkeras tensorflow
```

### Prompt 1C：hls4ml 综合配置生成

```
基于 QKeras INT8 量化模型（model_int8_qkeras.h5），请生成 cifar10_hls4ml_synthesis.ipynb：

任务：使用 hls4ml 将量化模型转换为 Vitis HLS 工程

代码要求：
1. 加载 QKeras 模型并用 hls4ml 解析
2. 配置 hls4ml config：
   - Backend: 'VivadoAccelerator'
   - Board: 'pynq-zu'（或手动指定 part: 'xczu4ev-sfvc784-1-i'）
   - Clock Period: 5ns（200MHz）
   - IOType: 'io_stream'（使用 AXI4-Stream 接口）
   - Reuse Factor: 4（平衡延迟与资源）
   - Strategy: 'Latency'
3. 调用 hls4ml.build() 执行 C-Simulation 和综合
4. 读取综合报告，提取并打印：
   - LUT / FF / DSP / BRAM 使用量及百分比（相对 88K LUT）
   - Latency（时钟周期数和实际时间 @200MHz）
   - Initiation Interval (II)
5. 生成资源对比 DataFrame 并输出为 resource_report.csv

注意：目标 LUT 使用率 < 60%（< 52K），留余量给 DMA 和 PS-PL 互联逻辑
```

---

## Phase 2 — Vivado Block Design 集成

### Prompt 2A：Block Design TCL 脚本

```
请生成一个完整的 Vivado TCL 脚本（create_block_design.tcl），用于在 Vivado 2022.2 中自动创建 EdgeAI-ZU4EV 项目的 Block Design。

目标板卡：XCZU4EV-1SFVC784I（ALINX ACU4EV）

Block Design 需要包含以下 IP 模块及连接：

1. Zynq UltraScale+ MPSoC（PS）
   - 使能 HP0 AXI Slave 接口（用于 DMA 访问 DDR）
   - 使能 GP0 AXI Master 接口（用于 PS 控制 DMA）
   - 使能 PL 时钟 pl_clk0 = 200MHz（给 AI 推理）
   - 使能 PL 时钟 pl_clk1 = 100MHz（给 DMA 控制）
   - 配置 DDR4 接口

2. AXI Direct Memory Access (AXI DMA)
   - 模式：Scatter Gather 禁用，Simple DMA
   - 数据宽度：64bit
   - 最大突发长度：256
   - 连接到 PS HP0 端口（数据通路）
   - 连接到 PS GP0 端口（控制通路）

3. HLS AI 推理 IP（占位符，待 hls4ml 生成后替换）
   - 名称：cifar10_accel_0
   - 接口：AXI4-Stream slave（输入图像）+ AXI4-Stream master（输出分类结果）
   - 连接：AXI DMA MM2S → 推理IP输入，推理IP输出 → AXI DMA S2MM

4. AXI SmartConnect
   - 连接 PS GP0 → DMA 控制口（AXI-Lite）
   - 连接 PS HP0 → DMA 数据口（AXI Full）

5. 时钟与复位
   - Processor System Reset（对应 200MHz 和 100MHz 各一个）
   - 连接所有 IP 的时钟和复位信号

TCL 脚本要求：
- 包含 create_project、create_bd_design、add IP、connect_bd 等完整命令
- 包含 validate_bd_design 和 save_bd_design
- 添加注释说明每个步骤的作用
- 最后生成 HDL Wrapper
- 输出文件名：create_block_design.tcl
```

### Prompt 2B：板卡约束文件 XDC

```
请生成 ALINX ACU4EV（XCZU4EV-1SFVC784I）的 Vivado 约束文件（acu4ev_constraints.xdc），包含：

1. 时钟约束
   - 创建主时钟约束（PS 时钟由 PS IP 自动管理，此处定义 PL 时钟）
   - pl_clk0 = 200MHz 时序约束
   - pl_clk1 = 100MHz 时序约束

2. PMOD/GPIO 引脚约束（按 ALINX ACU4EV 原理图）
   - LED 指示灯引脚（用于推理状态显示）：至少 4 个 LED
   - 如有 UART 调试接口，添加 UART TX/RX 约束

3. 时序例外
   - 跨时钟域路径的 set_false_path 或 set_max_delay 约束

4. 实现策略注释
   - 在文件头部注释说明推荐的 Vivado Implementation Strategy

注意：如果不确定具体引脚号，请标注 "# TODO: 查阅 ACU4EV 原理图确认引脚" 并给出合理的占位注释格式，不要凭空捏造引脚号。
```

---

## Phase 3 — Linux 板级部署（PetaLinux / devmem + AXI-DMA）

> **本项目已验证路径（2026-05）**  
> - FPGA 推理：`scripts/board_infer.py`（`/dev/mem` + AXI-DMA 寄存器编程，**无 PYNQ Overlay**）  
> - Bit 加载：`scripts/board_load_only.sh` / `fpga_manager`  
> - 一键部署：`scripts/board_ssh_deploy.py`（BOARD_IP=<your_board_ip>）  
> - CPU 基线：`scripts/cpu_baseline.py` + 手动安装 `tflite_runtime-2.5.0.post1`（`scripts/board_install_tflite_and_rerun.sh`）  
> - 板端实测：FPGA ~26 ms E2E，CPU 12.24 ms；**简历勿写 0.47× 加速比**，应写 DMA 瓶颈分析  
> - 板级验证路径：`scripts/board_infer.py` + `scripts/board_load_only.sh`（已删除 PYNQ notebook）

### Prompt 3A：（历史）PYNQ Overlay Notebook — 未采用，仅作 Prompt 模板保留

```
请生成完整的 Jupyter Notebook（board_deployment.ipynb），用于在 ACU4EV 板卡上（运行 PYNQ 或 Ubuntu + PYNQ 库）加载 bitstream 并执行推理：

前提条件：
- 板卡已运行 PYNQ-ZU 镜像（或 Ubuntu 22.04 + pynq pip 包）
- bitstream 文件：cifar10_accel.bit
- hwh 文件：cifar10_accel.hwh
- 量化模型权重（可选）

Notebook 内容要求：

Section 1: 加载 Overlay
- from pynq import Overlay
- overlay = Overlay('cifar10_accel.bit')
- 打印 IP 字典，确认 HLS IP 和 DMA 已加载
- 获取 dma 和 hls_accel 的句柄

Section 2: 准备输入数据
- 加载 CIFAR-10 测试集（10 张样例图片）
- 图像预处理：归一化到 INT8 范围（0~255 保持或归一化到 0~1）
- 分配 PYNQ 连续内存（pynq.allocate）：input_buffer 和 output_buffer

Section 3: 执行推理
- 将图像数据写入 input_buffer
- 启动 DMA 传输（dma.sendchannel 和 dma.recvchannel）
- 等待完成，读取 output_buffer
- 解析输出（10类 softmax 分数），取 argmax 得到预测类别

Section 4: 性能基准测试
- 使用 time.perf_counter() 测量单张推理延迟（重复100次取均值和std）
- 测量 ARM CPU 软件推理延迟（用 TensorFlow Lite 作为基线）
- 生成对比表格：FPGA 推理延迟 vs CPU 推理延迟 vs 加速比

Section 5: 批量精度测试
- 对 1000 张测试图片执行推理
- 计算 Top-1 精度
- 绘制混淆矩阵

Section 6: 结果可视化
- 显示 10 张测试图片 + 预测结果 + 置信度
- 生成 benchmark 柱状图（延迟对比）
- 保存板级结果到 `results/cpu_baseline.json`（CPU）; FPGA 延迟见 README Results（~26 ms E2E，`board_infer.py`）

代码风格：添加 markdown 说明，适合作为 GitHub Repo 展示
```

### Prompt 3B：ARM CPU 基线对比脚本

```
请生成 cpu_baseline.py，用于测量 ARM Cortex-A53 上的软件推理延迟作为 FPGA 加速比的基线：

要求：
1. 使用 TensorFlow Lite 加载量化模型（model_int8.tflite）
2. 对 CIFAR-10 100 张测试图片执行推理
3. 测量延迟（单张平均，单位 ms）
4. 测量吞吐（fps）
5. 记录 CPU 核心数和频率（读取 /proc/cpuinfo）
6. 将结果保存为 cpu_baseline.json：
   {
     "platform": "ARM Cortex-A53 @ 1.2GHz",
     "avg_latency_ms": ...,
     "std_latency_ms": ...,
     "throughput_fps": ...,
     "accuracy_top1": ...
   }
7. 添加将 .h5 模型转换为 .tflite 的代码段

此脚本在板卡的 PS 端（Linux 终端）运行，不依赖 PYNQ。
```

---

## Phase 4 — GitHub Repo 文档

### Prompt 4A：README.md 生成

```
请生成专业的 GitHub README.md，用于项目 EdgeAI-ZU4EV。

README 结构：

# EdgeAI-ZU4EV: Real-Time CNN Inference Accelerator on Zynq UltraScale+

## 项目简介（英文，约100字）
说明项目目标：在 ALINX ACU4EV（XCZU4EV）上实现端到端 CNN 推理加速，覆盖量化→HLS综合→SoC集成→板级部署完整链路。

## Hardware Platform
- 列出板卡规格表（LUT/DSP/BRAM/VCU/DDR等）

## System Architecture
- 用 ASCII 图或 Mermaid 图描述系统架构：
  CIFAR-10 Input → [PS: Python + devmem/AXI-DMA] → AXI DMA → [PL: HLS CNN Accelerator] → AXI DMA → [PS: 分类结果输出]
- 包含 VCU 视频流扩展方向的说明

## Results（核心展示，用表格）
实测数据（2026-05，ALINX ACU4EV）：
| Metric | Value |
|--------|-------|
| Test Accuracy (FP32) | 81.05 % |
| Test Accuracy (Q6 QKeras) | 79.43 % (Δ 1.62 pp) |
| CPU Top-1 (TFLite INT8) | 83.0 % |
| FPGA Inference Latency | ~26 ms (AXI-DMA E2E) |
| CPU Baseline (ARM A53) | 12.24 ms |
| Speedup | 0.47× *(repo only — CV 写 DMA 瓶颈分析，勿写加速比)* |
| LUT Utilization (full PL) | 24,702 / 88K (28.07%) |
| HLS IP LUT Utilization | 73,815 / 88K (83.88%) |
| DSP Utilization (full PL) | 39 / 728 (5.36%) |

## Resource Utilization（量化对比表）

## Getting Started
### Prerequisites
### Step 1: Model Training & Quantization
### Step 2: HLS Synthesis
### Step 3: Vivado Implementation
### Step 4: Board Deployment

## Project Structure（目录树）

## References（引用 hls4ml、QKeras、FINN 等论文和工具）

语言：英文（国际化）
风格：专业、简洁，参考 Xilinx/finn 和 fastmachinelearning/hls4ml 的 README 风格
```

### Prompt 4B：资源报告 Markdown 模板

```
请生成 results/resource_report.md，这是一个专业的资源利用率与性能报告模板（英文）：

内容：
1. 标题和测试环境说明（工具版本、板卡型号）
2. 模型架构摘要表
3. 量化精度对比表（Float32 / Q6 QKeras — 本仓库已测项）
4. HLS综合资源报告表：
   | Resource | Used | Available | Utilization |
   包含 LUT / LUTRAM / FF / DSP48 / BRAM_18K / URAM
   分两张表：HLS IP (csynth) vs 整设计 (Vivado impl)；口径说明见 resource_report.md §4
5. 时序性能表：
   | Metric | Value |
   包含 Clock Period / Latency (cycles) / Latency (ms) / Initiation Interval / Throughput (fps)
6. 与 CPU 基线对比的加速比分析段落（占位）
7. 结论段落（占位）

要求：格式规范、可直接作为 GitHub 展示文档
```

---

## Phase 5 — 扩展加分项（可选）

### Prompt 5A：VCU 视频流接入概念设计文档

```
请生成 docs/vcu_pipeline_design.md，描述将 VCU 视频解码与 PL 推理加速形成流水线的系统设计方案：

内容：
1. 系统概述：VCU → PL 推理 Pipeline 架构
2. 数据流设计：
   - VCU 解码 H.264 视频 → YUV 帧
   - YUV → RGB 色彩空间转换（PL 端 HLS 实现）
   - RGB 帧送入 CNN 推理 IP
   - 推理结果叠加 OSD（On-Screen Display）字幕
   - 输出带标注的视频流
3. 关键技术挑战与解决方案（缓冲管理、时序同步、带宽计算）
4. 带宽需求计算：
   1080p @30fps 的 YUV420 带宽 = ? Mbps
   计算是否超出 PL DDR4（1GB 16bit）的带宽上限
5. 实现路线图（分阶段）
6. 参考资料

语言：英文，技术文档风格
```

### Prompt 5B：hls4ml 自定义 Board JSON

```
请生成 hls4ml 自定义板卡配置文件，使 hls4ml 的 VivadoAccelerator 后端支持 XCZU4EV：

文件1：acu4ev.json（放在 hls4ml/backends/vivado/vivado_accelerator/boards/ 目录下）
内容参照 pynq-zu.json 格式，修改：
- part: "xczu4ev-sfvc784-1-i"
- board_name: "acu4ev"
- clock_period: 5（200MHz）
- LUT 资源数：88000
- DSP 资源数：728
- BRAM 资源数：252（4.5Mb / 18Kb per BRAM）

文件2：使用自定义板卡的 Python 示例代码片段（3-5行）

附说明：如何将此文件注册到本地安装的 hls4ml 中（pip install -e . 或直接复制路径）
```

---

## 使用建议

| Phase | 预计耗时 | 发给 Claude 的时机 |
|-------|----------|-------------------|
| Phase 1A + 1B | Day 1-2 | 先跑通训练和量化 |
| Phase 1C | Day 3 | 确认量化模型精度后 |
| Phase 2A + 2B | Day 5-7 | HLS综合完成后 |
| Phase 3A + 3B | Day 10-14 | Bitstream 生成后 |
| Phase 4A + 4B | Day 14 | 有实测数据后 |
| Phase 5（选做）| Day 20+ | 基础功能跑通后 |

---

*本 Prompt 文档为 EdgeAI-ZU4EV 项目技术路线与交付物模板。*
*硬件平台：ALINX ACU4EV / XCZU4EV-1SFVC784I*
