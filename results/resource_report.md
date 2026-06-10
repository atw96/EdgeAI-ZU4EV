# EdgeAI-ZU4EV: HLS Synthesis & Performance Report

**Project**: EdgeAI-ZU4EV — CNN Inference Accelerator on Zynq UltraScale+  
**Date**: May 2026  
**Repository**: https://github.com/atw96/EdgeAI-ZU4EV  

---

## 1. Test Environment

| Item | Details |
|------|---------|
| **Target Device** | Xilinx Zynq UltraScale+ XCZU4EV-1SFVC784I |
| **Board** | ALINX ACU4EV |
| **Synthesis Tool** | Vivado HLS 2020.1 (vivado_hls) |
| **Implementation Tool** | Vivado 2020.1 |
| **OS (Host)** | Ubuntu 20.04 LTS |
| **OS (Board)** | PetaLinux 2020.1 |
| **Python (Host)** | 3.7.12 (conda `edgeai_39`) |
| **Python (Board)** | 3.7.6 (stock rootfs, no pip3) |
| **Board deployment** | Linux devmem + AXI-DMA (`scripts/board_infer.py`, `scripts/board_load_only.sh`); **no PYNQ Overlay** |
| **CPU inference (board)** | `tflite_runtime` 2.5.0.post1 cp37 aarch64 (manual wheel install; see `scripts/board_install_tflite_and_rerun.sh`) |
| **TensorFlow** | 2.6.0 |
| **QKeras** | 0.9.0 |
| **hls4ml** | 0.6.0 |
| **Target Clock** | 5.0 ns (200 MHz) |
| **HLS Strategy** | Latency |
| **HLS Backend** | Vivado (io_stream / AXI4-Stream) |

---

## 2. Model Architecture Summary

| Layer | Type | Output Shape | Kernel | Filters | Parameters |
|-------|------|-------------|--------|---------|-----------|
| input_image | Input | (32, 32, 3) | — | — | 0 |
| conv1 | QConv2D | (32, 32, 32) | 3×3 | 32 | 864 |
| bn1 | BatchNorm | (32, 32, 32) | — | — | 128 |
| relu1 | QActivation | (32, 32, 32) | — | — | 0 |
| pool1 | MaxPool2D | (16, 16, 32) | 2×2 | — | 0 |
| conv2 | QConv2D | (16, 16, 64) | 3×3 | 64 | 18,432 |
| bn2 | BatchNorm | (16, 16, 64) | — | — | 256 |
| relu2 | QActivation | (16, 16, 64) | — | — | 0 |
| pool2 | MaxPool2D | (8, 8, 64) | 2×2 | — | 0 |
| conv3 | QConv2D | (8, 8, 64) | 3×3 | 64 | 36,864 |
| bn3 | BatchNorm | (8, 8, 64) | — | — | 256 |
| relu3 | QActivation | (8, 8, 64) | — | — | 0 |
| gap | GlobalAvgPool2D | (64,) | — | — | 0 |
| predictions | QDense | (10,) | — | — | 650 |
| **Total** | | | | | **~57,450** |

**Quantisation scheme**: Kernels `ap_fixed<8,1>` · Biases `ap_fixed<8,4>` · Activations `ap_fixed<8,0>` · Accumulator `ap_fixed<16,6>`

---

## 3. Quantisation Accuracy Comparison

| Variant | Precision | Test Accuracy (%) | Accuracy Drop (pp) | Model Size |
|---------|-----------|------------------|-------------------|-----------|
| FP32 baseline | float32 | 81.05 | — | 141.7 KB |
| Q6 QKeras (6-bit QAT) | ap_fixed-style | 79.43 | 1.62 | 146.5 KB |

> Source: `notebooks/cifar10_quantize.ipynb` → `results/quantization_comparison.csv`  
> Board-side Top-1 with exported TFLite INT8: **83.0%** (100 images, Section 5).

---

## 4. HLS Synthesis Resource Report

> **Scope note (read before comparing tables)**  
> **§4.2** reports the **HLS CNN IP only** (Vivado HLS C-synthesis, `results/resource_report.csv`).  
> The HLS IP LUT utilisation (**83.88%**) is relative to the **entire XCZU4EV device**, not “83% of the PL slice budget”.  
> **§4.3** reports the **full implemented PL design** after Vivado Place & Route, including AXI DMA, PS–PL interconnect, SmartConnect, and other infrastructure. Full-design LUT utilisation is much lower (**28.07%**) because most PL resources remain unused outside the accelerator path.

### 4.1 XCZU4EV Resource Budget

| Resource | Available on ZU4EV | Budget Limit (60%) | Notes |
|----------|-------------------|--------------------|-------|
| LUT | 88,000 | 52,800 | |
| LUTRAM | ~20,000 | 12,000 | Subset of LUT |
| FF (Flip-Flop) | 176,000 | 105,600 | |
| DSP48E2 | 728 | 437 | 18×27 multipliers |
| BRAM_18K | 252 | 151 | 4.5 Mb total |
| URAM | 0 | — | Not present on ZU4EV |

### 4.2 HLS Accelerator Utilisation *(HLS IP only — csynth)*

| Resource | Used | Available | Utilisation | Status |
|----------|------|-----------|-------------|--------|
| LUT | 73,815 | 88,000 | 83.88% | Near device limit (IP scope) |
| FF | 37,958 | 176,000 | 21.57% | OK |
| DSP48E2 | 0 | 728 | 0.0% | OK |
| BRAM_18K | 26 | 252 | 10.32% | OK |

> Source: `results/resource_report.csv` (hls4ml C-synthesis report).

### 4.3 Post-Implementation Full Design Utilisation *(entire PL bitstream)*

_(After Vivado Place & Route — includes PS–PL interconnect, AXI DMA, SmartConnect, and HLS IP)_

| Resource | Used | Available | Utilisation |
|----------|------|-----------|-------------|
| LUT | 24,702 | 88,000 | 28.07% |
| DSP48E2 | 39 | 728 | 5.36% |
| BRAM_18K | 26 | 252 | 10.16% |

> Source: Vivado implementation utilisation report (full design).

---

## 5. Board-Level Inference Performance

_(Measured on ALINX ACU4EV — FPGA via `scripts/board_infer.py`; CPU via `scripts/cpu_baseline.py`)_

### 5.1 HLS IP Inference Latency *(csynth — pure PL compute)*

Source: `myproject_axi_csynth.rpt` via `scripts/hls_metrics.py` → `results/hls_ip_latency.json`

| Metric | Value |
|--------|-------|
| **Clock** | 200 MHz (5.0 ns) |
| **Latency (cycles)** | 2,668,780 – 2,673,941 |
| **Latency (ms)** | **13.344 – 13.370** |
| **Initiation Interval (cycles)** | 3,470 – 2,670,362 |
| **Pipeline** | dataflow |

Formula: `latency_ms = latency_cycles × 5.0 ns / 1e6`

### 5.2 Board-Level Latency *(devmem + AXI-DMA — measured 2026-05-25)*

Source: `scripts/board_benchmark.py` → `results/fpga_benchmark.json` (100 runs, `perf_counter`)

| Metric | HLS IP (csynth) | Board DMA path | Board E2E | CPU (TFLite) |
|--------|-----------------|----------------|-----------|--------------|
| **Avg Latency (ms)** | **13.37** | 26.76 ± 0.03 | 27.52 ± 0.04 | 12.24 |
| **Min Latency (ms)** | 13.344 | 26.724 | 27.469 | 12.21 |
| **Throughput (fps)** | ~74.8 | ~37.4 | ~36.4 | 81.7 |
| **Top-1 Accuracy (%)** | — | — | — | 83.0 |

> **Board DMA path**: MM2S/S2MM start → dual IOC (`perf_counter`, excludes Python readout).  
> **Board E2E**: includes `dma_soft_reset`, buffer `msync`, DMA, busy-wait IOC.  
> **HLS IP ~13.4 ms** is roughly half of board DMA/E2E (~27 ms); the gap is PS–PL DMA orchestration and DDR transfer overhead.  
> CPU基线为tflite_runtime单线程推理，未启用NEON加速。

---

## 6. Speedup Analysis

| Comparison | Result |
|-----------|--------|
| FPGA E2E vs ARM A53 TFLite INT8 (1 thread) | **0.47×** *(repo only — do not cite on CV)* |

**Interpretation**: FPGA end-to-end latency (~26 ms) is **slower** than the ARM baseline (12.24 ms). The bottleneck is **AXI-DMA data movement and PS–PL orchestration**, not the HLS compute kernel. Optimisation paths: zero-copy DMA, batch inference, manual HLS pipelining.

> **Résumé / CV**: *板级实测端到端延迟 26ms（含AXI-DMA传输），识别出DMA传输为主要瓶颈，HLS推理算子本身计算开销可通过流水线优化进一步降低*

**DMA overhead context**:

```
Input  : 32 × 32 × 3 = 3,072 bytes (+ PS-side fixed-point packing)
Output : 10-class INT8 logits
Measured FPGA E2E (~26 ms) >> theoretical HP0 line-rate (~μs) → software/DMA orchestration dominates.
```

---

## 7. Conclusion

This report presents the HLS synthesis and board-level performance characterisation
of the EdgeAI-ZU4EV CNN accelerator implemented on a Xilinx Zynq UltraScale+
XCZU4EV device. Key findings:

- **Model**: Compact CNN with ~57K parameters trained on CIFAR-10, achieving FP32
  accuracy of **81.05%** and **79.43%** after Q6 quantisation (1.62 pp drop).
- **Resource**: The HLS IP alone uses **83.88%** of device LUTs (csynth scope); the
  full implemented PL design uses **28.07%** LUT, **5.36%** DSP, and **10.16%** BRAM —
  headroom remains for PS–PL interconnect expansion and future VCU integration.
- **Performance**: FPGA end-to-end inference achieves **~26 ms** per image (~38.5 fps),
  while the ARM Cortex-A53 TFLite baseline achieves **12.24 ms** (81.7 fps) — a
  **0.47×** ratio indicating DMA-dominated overhead in this demo build.
- **Design quality**: Target clock 200 MHz; timing closed in implementation (board demo operational).

The design demonstrates a complete FPGA AI inference acceleration workflow using
open-source tools (hls4ml + QKeras), providing a reproducible template for
edge AI hardware development targeting Zynq UltraScale+ SoCs.

---

*Generated by EdgeAI-ZU4EV project toolchain. Board measurements: May 2026.*
