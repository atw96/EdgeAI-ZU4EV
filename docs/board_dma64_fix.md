# 板端 DRAM 对齐修复记录（DMA 64-bit + HP0 运行时 64-bit）

**日期：** 2026-07-06  
**状态：** 已验收 — 板端 N=100 Top-1 **82%**（对齐 HLS csim）

---

## 问题回顾

| 现象 | 说明 |
|------|------|
| 0xAA 预填诊断 | 24 word 中 12 个仍为 `0xAAAAAAAA`（洞） |
| GAP 回读 | 仅 12 维有效，其余为 0 |
| N=100 Top-1 | 约 26%（软件 hole 解码后） |
| ILA / csim | HLS 出口与仿真均为 82%，排除模型问题 |

**根因：** 32-bit DMA M_AXI 写入经 64-bit HP0_FPD 时产生稀疏 DRAM 布局；`fpga_manager` 加载后 AFIFM2 默认 32-bit 写会加剧该问题。

---

## 修复方案（两步缺一不可）

### 1. Bitstream：DMA M_AXI 64-bit

**文件：** `tcl/create_block_design.tcl`

- `DMA_M_AXI_DATA_WIDTH` 32 → **64**
- `c_include_mm2s_dre` / `c_include_s2mm_dre` → **0**（MM 64-bit、AXIS 32-bit，无需 DRE）
- DMA 数据路径：SmartConnect → `S_AXI_HP0_FPD`

**重建：**

```bash
source /tools/Xilinx/Vivado/2020.1/settings64.sh
export FORCE_REBUILD=1 HLS_OUTPUT_AXIS_BITS=32
bash scripts/rebuild_bitstream.sh
```

### 2. 运行时：HP0 fabric 64-bit（AR66295）

**文件：** `scripts/board_fix_hp0_width.py`

`fpga_manager` 加载 PL 后，将 AFIFM2 RD/WR 控制寄存器 `bits[1:0]` 设为 `01`（64-bit）。

**错误做法（旧版脚本）：** 设为 32-bit 写（`wr→0x3b2`）会在 DMA 64-bit 场景下再现洞布局。

`board_load_only.sh` 在检测到板上存在该脚本时会自动调用。

---

## 验收结果

详见 `results/board_dma64_verify_summary.json`。

| 检查项 | 结果 |
|--------|------|
| hwh `c_m_axi_s2mm_data_width` | 64 |
| hwh `s_axis_s2mm_tdata_width` | 32 |
| 0xAA 洞检测 | `aa_word_indices: []` |
| board vs csim GAP | 24/24 匹配 |
| N=10 Top-1 | 90% |
| N=100 Top-1 | **82%** |
| DMA 延迟 | ~57 ms |

**deploy MD5（2026-07-06 构建）：**

| 文件 | MD5 |
|------|-----|
| `cifar10_accel.bit` | `46987907f8177883048b705fdf68c370` |
| `cifar10_accel.hwh` | `7576e1edbc8708cdaad98bbaa1f50baa` |

---

## 板端验证步骤

```bash
export BOARD_IP=<your-board-ip>
export BOARD_PASS=<your-ssh-password>   # 或使用 SSH 密钥，勿写入仓库

# 部署
scp deploy/cifar10_accel.bit scripts/board_fix_hp0_width.py \
    scripts/board_load_only.sh scripts/dma_infer_common.py \
    root@${BOARD_IP}:/tmp/edgeai_bench/

# 加载 PL
ssh root@${BOARD_IP} \
  "cp /tmp/edgeai_bench/cifar10_accel.bit /lib/firmware/ && \
   FORCE_PL_RELOAD=1 sh /tmp/edgeai_bench/board_load_only.sh"

# HP0 64-bit + 0xAA 硬门槛（必须先过）
ssh root@${BOARD_IP} \
  "python3 /tmp/edgeai_bench/board_fix_hp0_width.py; \
   cd /tmp/edgeai_bench; \
   OUT_DIM=24 OUT_BYTES=96 OUTPUT_PACK_MODE=serial \
   BENCH_NPZ=/tmp/edgeai_bench/cifar10_bench.npz \
   python3 board_aa_serial96_diag.py"
# 期望：hp0_width_fix ...->0x...b1；0xAAAAAAAA indices: []

# N=100 benchmark
ssh root@${BOARD_IP} \
  "python3 /tmp/edgeai_bench/board_fix_hp0_width.py; \
   cd /tmp/edgeai_bench; \
   OUT_DIM=24 OUT_BYTES=96 OUT_LAYOUT=gap_ps OUT_FIXED_SCALE=1024 \
   OUTPUT_PACK_MODE=serial DENSE_NPZ=dense_head.npz N_ACCURACY=100 \
   python3 board_benchmark.py"
```

---

## 已知限制

- 每次上电 / `fpga_manager` 重载 bit 后须重新执行 HP0 64-bit 设置（或由 `board_load_only.sh` 自动执行）。
- 长期方案：在 FSBL / `psu_init` 中固化 AFIFM2 64-bit，避免依赖运行时 devmem。

---

## 相关文件

| 路径 | 说明 |
|------|------|
| `tcl/create_block_design.tcl` | DMA 64-bit BD 配置 |
| `tcl/run_impl_and_bitstream.tcl` | 综合前设置 `system_wrapper` top |
| `scripts/board_fix_hp0_width.py` | HP0 64-bit 运行时修复 |
| `scripts/board_aa_serial96_diag.py` | 0xAA 洞布局诊断 |
| `results/board_s2mm_freshness_diag.json` | 修复前 B1 诊断 |
