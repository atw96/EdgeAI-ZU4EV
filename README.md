# EdgeAI-ZU4EV: Real-Time CNN Inference Accelerator on Zynq UltraScale+

[![Vivado](https://img.shields.io/badge/Vivado-2020.1-blue?logo=xilinx)](https://www.xilinx.com/products/design-tools/vivado.html)
[![PetaLinux](https://img.shields.io/badge/PetaLinux-2020.1-blue?logo=linux)](https://www.xilinx.com/products/design-tools/embedded-software/petalinux-sdk.html)
[![hls4ml](https://img.shields.io/badge/hls4ml-0.6.x-green)](https://fastmachinelearning.org/hls4ml/)
[![Python](https://img.shields.io/badge/Python-3.7+-yellow)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-lightgrey)](LICENSE)

**End-to-end CNN inference on Zynq UltraScale+:** QKeras Q6 quantization → hls4ml HLS synthesis → Vivado Block Design → PetaLinux board deployment (devmem + AXI-DMA)

## Overview

EdgeAI-ZU4EV demonstrates an end-to-end CNN inference acceleration pipeline on the **ALINX ACU4EV** board (Xilinx Zynq UltraScale+ XCZU4EV). The project covers the full hardware–software co-design stack: model quantisation with QKeras → HLS synthesis with hls4ml → Vivado Block Design integration → on-board deployment via Linux devmem and AXI-DMA on PetaLinux 2020.1 (no PYNQ dependency). A compact CIFAR-10 classifier (<100K parameters) is synthesised to an AXI4-Stream HLS accelerator and benchmarked against the quad-core ARM Cortex-A53 baseline.

---

## Hardware Platform

| Resource | Specification |
|----------|--------------|
| **SoC** | Xilinx Zynq UltraScale+ XCZU4EV-1SFVC784I |
| **LUT** | 88,000 |
| **DSP48E2** | 728 |
| **BRAM** | 4.5 Mb (252 × BRAM_18K) |
| **PS DDR4** | 4 GB, 64-bit |
| **PL DDR4** | 1 GB, 16-bit |
| **VCU** | H.264 / H.265 hardware encoder–decoder |
| **PS CPU** | ARM Cortex-A53 (quad-core, 1.33 GHz) + Cortex-R5 (dual-core) |
| **Development tools** | Vivado 2020.1 / Vivado HLS 2020.1 / PetaLinux 2020.1 |

---

## System Architecture

```
+---------------------------------------------------------------------+
|                        Zynq UltraScale+ SoC                          |
|                                                                      |
|  +------------------------------+  +-----------------------------+  |
|  |   Processing System (PS)   |  |  Programmable Logic (PL)    |  |
|  |                              |  |                             |  |
|  |  ARM Cortex-A53 (4-core)     |  |  +-----------------------+  |  |
|  |  +------------------------+  |  |  | HLS CNN Accel         |  |  |
|  |  | Python + devmem        |  |  |  | (hls4ml INT8)         |  |  |
|  |  | 1. Load CIFAR-10 image |  |  |  | Conv2D x3             |  |  |
|  |  | 2. DMA transfer -> PL    |  |  |  | MaxPool x2            |  |  |
|  |  | 3. Receive result <- PL |  |  |  | GAP + Dense           |  |  |
|  |  | 4. argmax -> label      |  |  |  +----------+----------+  |  |
|  |  +-----------+------------+  |  |             |          |  |  |
|  |              |        ^      |  |  +----------v----------+  |  |
|  |  +-----------v--------+      |  |  | AXI4-Stream I/O     |  |  |
|  |  | AXI DMA (Simple)   |<---->|  |  | 32x32x3 in          |  |  |
|  |  | MM2S / S2MM        |      |  |  | 10-class out        |  |  |
|  |  +--------------------+      |  |  +---------------------+  |  |
|  |  HP0 AXI Slave (200 MHz)     |  |                             |  |
|  +------------------------------+  +-----------------------------+  |
+---------------------------------------------------------------------+
         |
         |  Future: VCU H.264 decode -> YUV->RGB (PL HLS) ->
         |  CNN accelerator -> OSD overlay -> annotated video
         +-- See docs/vcu_pipeline_design.md
```

**Data flow**: CIFAR-10 image → PS Python → AXI DMA (MM2S, 200 MHz) →  
AXI4-Stream → HLS CNN Accelerator → AXI4-Stream → AXI DMA (S2MM) →  
PS Python → classification result (Top-1 label + confidence)

---

## Results

| Metric | Value |
|--------|-------|
| **Test Accuracy (FP32 baseline)** | 81.05 % |
| **Test Accuracy (Q6 QKeras, 6-bit QAT)** | 79.43 % (Δ 1.62 pp) |
| **CPU Top-1 Accuracy (TFLite INT8, 100 imgs)** | 83.0 % |
| **FPGA Inference Latency** | ~26 ms (AXI-DMA end-to-end) |
| **CPU Baseline (ARM A53, TFLite INT8)** | 12.24 ms @ 1066 MHz |
| **Speedup (FPGA vs CPU)** | 0.47× *(repo only — see note below)* |
| **LUT Utilisation (full PL design)** | 24,702 / 88,000 (28.07%) |
| **HLS IP LUT Utilisation** | 73,815 / 88,000 (83.88%) — see [resource_report.md](results/resource_report.md) |
| **DSP48E2 Utilisation (full PL design)** | 39 / 728 (5.36%) |
| **BRAM_18K Utilisation (full PL design)** | 26 / 252 (10.16%) |

#### Performance Analysis

当前 FPGA 端到端延迟（26 ms）高于 CPU 基线（12.2 ms），瓶颈在于 AXI-DMA 数据搬运而非 HLS 推理算子本身。优化方向：

1. 零拷贝 DMA（减少 PS–PL 数据搬运次数）
2. 批量推理（batch inference，摊薄 DMA 开销）
3. HLS 手动流水线优化（替代 hls4ml 自动生成代码）

> **Resume / CV wording (do not put "0.47× speedup" on a résumé)**  
> This repo reports the measured ratio honestly for engineering transparency. On a CV, describe the bottleneck analysis instead, e.g.:  
> *「板级实测端到端延迟 26 ms（含 AXI-DMA 传输），识别出 DMA 传输为主要瓶颈，HLS 推理算子本身计算开销可通过流水线优化进一步降低」*

---

## Resource Utilisation

*Full implemented PL design (Vivado impl). HLS IP-only utilisation differs — see [results/resource_report.md](results/resource_report.md) §4.2.*

| Resource | Used | Available | Utilisation |
|----------|------|-----------|-------------|
| LUT | 24,702 | 88,000 | 28.07% |
| LUTRAM | — | — | — |
| FF | — | 176,000 | — |
| DSP48E2 | 39 | 728 | 5.36% |
| BRAM_18K | 26 | 252 | 10.16% |

---

## Getting Started

### Prerequisites

**Host PC (Linux)**

```bash
# Xilinx tools (install separately from Xilinx Download Centre)
Vivado 2020.1 + Vivado HLS 2020.1
PetaLinux 2020.1

# Python environment
conda create -n edgeai python=3.7
conda activate edgeai
pip install tensorflow==2.6.0 qkeras hls4ml[profiling] \
            numpy pandas matplotlib seaborn scikit-learn jupyter
```

**Board (PetaLinux 2020.1, Python 3.7.6 — no pip3 on stock image)**

```bash
# tflite_runtime must be installed manually (cp37 aarch64 wheel)
# Run from WSL/host after syncing the repo:
bash scripts/board_install_tflite_and_rerun.sh
```

FPGA inference uses `scripts/board_infer.py` (devmem + AXI-DMA register programming), not PYNQ Overlay. See `scripts/board_ssh_deploy.py` for one-shot deploy from Windows/WSL.

---

### Step 1: Model Training & Quantisation

```bash
cd notebooks/
jupyter notebook cifar10_train.ipynb       # Phase 1A: FP32 training (>80% accuracy)
jupyter notebook cifar10_quantize.ipynb    # Phase 1B: Q6 QKeras quantisation (-> model_int8_qkeras.h5)
```

**Outputs**: `model_fp32.h5`, `model_int8_qkeras.h5`, `results/quantization_comparison.png`

---

### Step 2: HLS Synthesis (Vivado HLS 2020.1)

Ensure `vivado_hls` is in your PATH:

```bash
source /tools/Xilinx/Vivado/2020.1/settings64.sh
```

```bash
jupyter notebook cifar10_hls4ml_synthesis.ipynb   # Phase 1C
```

**Outputs**: `hls4ml_prj/` HLS project, `results/resource_report.csv`

The HLS IP is exported to:

```
hls4ml_prj/myproject_prj/solution1/impl/ip/
```

---

### Step 3: Vivado 2020.1 Block Design & Implementation

```bash
source /tools/Xilinx/Vivado/2020.1/settings64.sh

# Auto-create Block Design
vivado -mode batch -source tcl/create_block_design.tcl

# Or open Vivado GUI and source the script:
# Tcl Console -> source tcl/create_block_design.tcl
```

Add constraints, then run implementation:

```tcl
add_files -fileset constrs_1 constraints/acu4ev_constraints.xdc
launch_runs impl_1 -to_step write_bitstream -jobs 8
```

**Outputs**: `deploy/cifar10_accel.bit`, `deploy/cifar10_accel.hwh` (via `tcl/run_impl_and_bitstream.tcl` or `scripts/rebuild_bitstream.sh`)

---

### Step 4: Board Deployment (PetaLinux 2020.1)

```bash
# One-shot deploy from Windows/WSL (bit + CPU/FPGA scripts)
python scripts/board_ssh_deploy.py   # BOARD_IP=<your_board_ip>

# Or manually on board after scp:
ssh root@<board_ip>
python3 cpu_baseline.py              # CPU baseline (needs tflite_runtime — see above)
python3 board_infer.py               # FPGA inference (devmem + AXI-DMA)
```

`scripts/board_infer.py` + `scripts/board_load_only.sh` are the verified board demo path.

---

## Project Structure

```
EdgeAI-ZU4EV/
├── notebooks/
│   ├── cifar10_train.ipynb            # Phase 1A: FP32 training
│   ├── cifar10_quantize.ipynb         # Phase 1B: Q6 QKeras quantisation
│   └── cifar10_hls4ml_synthesis.ipynb # Phase 1C: HLS synthesis
├── tcl/
│   └── create_block_design.tcl        # Phase 2A: Vivado BD automation
├── constraints/
│   └── acu4ev_constraints.xdc         # Phase 2B: Timing constraints
├── deploy/
│   ├── cifar10_accel.bit / .hwh / .xsa
│   └── DEPLOY_README.txt
├── scripts/
│   ├── board_infer.py                 # FPGA inference (devmem + AXI-DMA)
│   ├── board_load_only.sh             # Load bitstream via fpga_manager
│   ├── board_ssh_deploy.py            # One-shot deploy from host
│   ├── cpu_baseline.py                # ARM A53 TFLite baseline
│   ├── export_tflite.py / gen_board_samples.py  # Host-side deploy artifacts
│   └── board_install_tflite_and_rerun.sh        # tflite_runtime install + CPU baseline
├── results/
│   ├── cpu_baseline.json              # Board CPU baseline (measured)
│   ├── resource_report.csv / .md
│   └── quantization_comparison.csv
├── docs/
│   └── vcu_pipeline_design.md         # Future VCU extension (design only)
├── hls4ml_board/
│   └── acu4ev.json
├── LICENSE
└── README.md
```

---

## References

1. **hls4ml**: Duarte, J. et al. *Fast inference of deep neural networks in FPGAs for particle physics.* JINST 13 (2018). [arxiv:1804.06913](https://arxiv.org/abs/1804.06913)
2. **QKeras**: Coelho, C. et al. *Automatic heterogeneous quantization of deep neural networks for low-latency inference on the edge.* Nature Electronics (2021). [arxiv:2006.10159](https://arxiv.org/abs/2006.10159)
3. **FINN**: Blott, M. et al. *FINN-R: An End-to-End Deep-Learning Framework for Fast Exploration of Quantized Neural Networks.* ACM TRETS (2018). [arxiv:1809.04570](https://arxiv.org/abs/1809.04570)
4. **Zynq UltraScale+ Product Guide**: [PG338](https://docs.xilinx.com/r/en-US/ug1085-zynq-ultrascale-trm)
5. **AXI DMA Product Guide**: [PG021](https://docs.xilinx.com/r/en-US/pg021-axi-dma) — PS–PL data path used in this demo (devmem register programming)
6. **fastmachinelearning/hls4ml**: [https://github.com/fastmachinelearning/hls4ml](https://github.com/fastmachinelearning/hls4ml)

---

## License

MIT License — see [LICENSE](LICENSE) for details.
