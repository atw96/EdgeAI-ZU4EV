# EdgeAI-ZU4EV: Real-Time CNN Inference Accelerator on Zynq UltraScale+

[![Vivado](https://img.shields.io/badge/Vivado-2020.1-blue?logo=xilinx)](https://www.xilinx.com/products/design-tools/vivado.html)
[![PetaLinux](https://img.shields.io/badge/PetaLinux-2020.1-blue?logo=linux)](https://www.xilinx.com/products/design-tools/embedded-software/petalinux-sdk.html)
[![hls4ml](https://img.shields.io/badge/hls4ml-1.3-green)](https://fastmachinelearning.org/hls4ml/)
[![Python](https://img.shields.io/badge/Python-3.9+-yellow)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-lightgrey)](LICENSE)

**End-to-end CNN inference on Zynq UltraScale+:** QKeras Q6 QAT → hls4ml 1.3 HLS (`bit_exact`) → Vivado Block Design → PetaLinux board deployment (devmem + AXI-DMA)

## Overview

EdgeAI-ZU4EV demonstrates an end-to-end CNN inference acceleration pipeline on the **ALINX ACU4EV** board (Xilinx Zynq UltraScale+ XCZU4EV). A compact CIFAR-10 classifier (~19K parameters, 16/20/24 channels) is quantized with QKeras, synthesized via **hls4ml 1.3** with **GAP-only PL export** and PS-side Dense head, then integrated into Vivado and benchmarked on PetaLinux 2020.1 (no PYNQ).

**Current accuracy work (v19 Route 1):** Keras bench ~81%, HLS csim + PS Dense ~12% — see [docs/v19_route1_status.md](docs/v19_route1_status.md).

---

## Hardware Platform

| Resource | Specification |
|----------|--------------|
| **SoC** | Xilinx Zynq UltraScale+ XCZU4EV-1SFVC784I |
| **LUT** | 88,000 |
| **DSP48E2** | 728 |
| **BRAM** | 4.5 Mb (252 × BRAM_18K) |
| **PS DDR4** | 4 GB, 64-bit |
| **PS CPU** | ARM Cortex-A53 (quad-core) |
| **Tools** | Vivado / Vivado HLS 2020.1, PetaLinux 2020.1 |

---

## v19 Route 1 Pipeline (recommended)

GAP-only export, `input_qact` in QAT graph, `bit_exact=True`, **no manual PREC patches** (Plan B retired).

```bash
# WSL — QAT fine-tune (edgeai_39) + convert (edgeai_hls4ml13) + csim gates
cd EdgeAI-ZU4EV_Claude
source ~/miniconda3/etc/profile.d/conda.sh

FT_EPOCHS=40 CSIM_TOP1_MIN=75 N_ACCURACY=100 \
  bash scripts/run_v19_qat_resume.sh

# Monitor
tail -f results/v19_qat_pipeline.log
cat results/v19_route1_gates.json
```

| Script | Role |
|--------|------|
| `scripts/run_v19_qat_resume.sh` | Main: finetune → bit_exact convert → HLS patches → csim → Top-1 gate |
| `scripts/v19_qat_input_qact_finetune.py` | Add `input_qact` + short QAT fine-tune |
| `scripts/v19_bitexact_convert.py` | hls4ml 1.3 GAP-only convert |
| `scripts/v19_csim_route1_gates.py` | Top-1 primary gate; MAE auxiliary |
| `scripts/ensure_edgeai39_protobuf.sh` | protobuf 3.20.x for TF 2.6 |
| `scripts/cleanup_repo_for_git.sh` | Remove obsolete scripts / run caches before commit |

**Environments:** `edgeai_39` (TF 2.6 + QKeras, Vivado csim), `edgeai_hls4ml13` (hls4ml 1.3 convert). Setup: `scripts/setup_hls4ml13_env.sh`.

**Export layout:** `OUT_DIM=24 OUT_BYTES=92 OUT_LAYOUT=gap_ps OUT_FIXED_SCALE=256`

---

## Results (baseline measurements)

| Metric | Value |
|--------|-------|
| **Test Accuracy (FP32)** | 81.05 % |
| **Q6 QKeras (bench)** | ~80–84 % |
| **FPGA E2E latency** | ~26 ms (AXI-DMA) |
| **CPU baseline (TFLite INT8)** | 12.24 ms @ 1066 MHz |
| **PL LUT (full design)** | 24,702 / 88,000 (28.07 %) |

See [results/resource_report.md](results/resource_report.md) for HLS IP utilisation.

---

## Getting Started

### Prerequisites

```bash
# Host: Vivado 2020.1 + Vivado HLS 2020.1, PetaLinux 2020.1
# Conda: edgeai_39 (QAT), edgeai_hls4ml13 (hls4ml 1.3)
bash scripts/setup_hls4ml13_env.sh
```

### Model training & quantization

```bash
cd notebooks/
jupyter notebook cifar10_train.ipynb      # model_fp32.h5, model_teacher.h5
jupyter notebook cifar10_quantize.ipynb   # model_int8_qkeras.h5
```

### HLS synthesis

Notebook `cifar10_hls4ml_synthesis.ipynb` or Route 1 automation above. Generated project: `notebooks/hls4ml_prj/` (gitignored; rebuild from notebook/scripts).

### Vivado & board

```bash
source /tools/Xilinx/Vivado/2020.1/settings64.sh
vivado -mode batch -source tcl/create_block_design.tcl
# bitstream: scripts/rebuild_bitstream.sh or tcl/run_impl_and_bitstream.tcl

python scripts/board_ssh_deploy.py   # BOARD_IP=<ip>
```

Board path: `scripts/board_load_only.sh`, `scripts/board_infer.py`, `scripts/cpu_baseline.py`.

---

## Project Structure

```
EdgeAI-ZU4EV/
├── notebooks/          # Train / quantize / HLS notebooks + model .h5
├── scripts/            # Route 1 pipeline, HLS patches, board deploy
├── tcl/                # Vivado Block Design
├── constraints/        # Timing XDC
├── deploy/             # bit/hwh/xsa, bench npz (npz gitignored)
├── results/            # Metrics JSON/CSV (see .gitignore for large artifacts)
├── docs/
│   ├── v19_route1_status.md   # Current debug status
│   └── vcu_pipeline_design.md
└── README.md
```

---

## References

1. [hls4ml](https://fastmachinelearning.org/hls4ml/) — Duarte et al., JINST 13 (2018)
2. [QKeras](https://github.com/google/qkeras) — Coelho et al., Nature Electronics (2021)
3. [Zynq UltraScale+ TRM](https://docs.xilinx.com/r/en-US/ug1085-zynq-ultrascale-trm) (PG338)
4. [AXI DMA PG021](https://docs.xilinx.com/r/en-US/pg021-axi-dma)

---

## License

MIT License — see [LICENSE](LICENSE).
