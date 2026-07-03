# ILA 核验计划：output_stream

## MM2S 对比结论

- **判定**: INPUT OK — `npz == tb_input == board CMA`；问题在 PL 输出路径
- **主机 npz vs csim tb_input**: 全部一致 (N=10)
- **板端 CMA 回读 vs npz**: 一致
- **board_safe_verify 输出**: DMA IOC 成功，但 **match 0/24**；DRAM 仍呈 slot 空洞
  - 板端 `board_words[0:8]=[511, 1708, 0, 0, 1019, 1437, 0, 0]`
  - csim `csim_words[0:8]=[940, 820, 708, 1678, 704, 687, 1283, 2421]`

## 当前状态摘要

| 项 | 值 |
|----|-----|
| 板子 IP | `BOARD_IP` 环境变量 |
| 工程根 | 仓库根目录 |
| deploy bit MD5 | `7969e6a7b04af3d6a39de4d47f3bee58`（与 `impl_1/system_wrapper.bit` 一致，2026-06-30 impl） |
| `deploy/cifar10_accel.ltx` | **过期，不可用于当前 bit**（见下节） |
| 串口（备用） | 板载 UART，115200 |

## deploy 产物同源校验（重要）

`ls deploy/` 里**有** `cifar10_accel.ltx`，但**不是**当前 bit 的配套文件：

| 文件 | 修改时间 | MD5 / 大小 | 与当前 bit 同源？ |
|------|----------|------------|-------------------|
| `cifar10_accel.bit` | 2026-07-01 | `7969e6a7…`，5 463 200 B | ✅ 基准 |
| `cifar10_accel.hwh` | 2026-06-30 | 460 673 B | ✅ 同轮 impl |
| `cifar10_accel.ltx` | **2026-05-26** | `dabaf723…`，5 582 B | ❌ **过期** |
| `debug_nets.ltx` | 2026-05-26 | 与 `cifar10_accel.ltx` **完全相同** | ❌ 旧副本 |
| `system_wrapper.ltx` | 2026-05-26 | 与上 **完全相同** | ❌ 旧副本 |

`vivado_project/.../impl_1/` 下**没有** `system_wrapper.ltx` → 2026-06-30 这轮 impl **未导出** debug probes。

**结论**：

1. **禁止**用 5/26 的 `cifar10_accel.ltx` 配当前 bit（探针与网表不一致）。
2. 当前 BD **很可能未含 ILA** → 需先 `add_dma_ila.tcl`（并扩展 output_stream 探针）再重编。
3. 重编后执行 `write_debug_probes`，使 bit 与 ltx **同日同源**。

## 硬性守则（防 SSH 挂死）

1. 板子重启后 **必须先** `FORCE_PL_RELOAD=1 sh board_load_only.sh`，确认 `fpga0 state=operating`
2. **禁止**在未加载 PL 时跑 `board_read_cma_input` / `board_fetch_gap` / 任何 `/dev/mem` 脚本
3. **禁止**默认跑 `board_s2mm_scan`、N=100 `board_benchmark`
4. 板端脚本 **仅在 WSL 内** ssh/scp；禁止 PowerShell 直接跑带引号的 python ssh
5. 上板前可调 MCP：`pre_board_devmem_guard(require_pl=true)` 或 `precompile_guard(stage=board_verify)`

---

## 操作清单（从 Windows 开始）

### 阶段 0：Windows 环境与连线（约 10 分钟）

#### 0.1 硬件连接

| 接口 | 用途 |
|------|------|
| 网线 | 板子 → 路由器/PC，IP 由 `BOARD_IP` 指定 |
| USB JTAG | Platform Cable / 板载 JTAG → **Windows** USB（ILA 必需） |
| 串口 COM3（可选） | 115200，SSH 不通时看启动日志 |

#### 0.2 打开两个终端

**终端 A — Windows PowerShell**（ping / Vivado GUI）

```powershell
ping ${BOARD_IP}
```

**终端 B — WSL**（所有 ssh/scp/板端脚本）

```powershell
wsl -d Ubuntu-18.04
# 在仓库根目录
conda activate <your-env>
```

期望：`ping` 通；WSL 能 `ssh root@${BOARD_IP}`。

#### 0.3 确认 PL 状态（WSL）

```bash
ssh -o ConnectTimeout=8 -o StrictHostKeyChecking=no \
  -o UserKnownHostsFile=/dev/null root@${BOARD_IP} \
  'cat /sys/class/fpga_manager/fpga0/state'
```

- `operating` → 可继续
- `unknown` → **必须先** `board_load_only`，禁止 devmem

---

### 阶段 A：生成与当前 bit 同源的 bit + ltx（WSL 内）

> `deploy/cifar10_accel.ltx`（5/26）**已作废**；`impl_1` 无新 ltx。必须重走本阶段。

#### A.1 确认无可用 ltx

```bash
ls -la deploy/cifar10_accel.{bit,ltx}
md5sum deploy/cifar10_accel.bit deploy/cifar10_accel.ltx
stat -c '%y %n' deploy/cifar10_accel.bit deploy/cifar10_accel.ltx
# bit 应为 2026-06/07；ltx 若为 2026-05-26 → 不同源，不可用

ls vivado_project/EdgeAI_ZU4EV.runs/impl_1/system_wrapper.ltx 2>/dev/null || echo "impl 无 ltx"
```

#### A.2 向 BD 加 ILA 并重编（约 30–90 分钟）

```bash
# 在仓库根目录
source /tools/Xilinx/Vivado/2020.1/settings64.sh

# 现有脚本仅接 DMA 复位/valid 探针；output_stream 需扩展 TCL 后再跑
vivado -mode batch -source tcl/add_dma_ila.tcl

FORCE_REBUILD=1 vivado -mode batch -source tcl/run_impl_and_bitstream.tcl
# export_bitstream.tcl 会尝试 write_debug_probes → deploy/cifar10_accel.ltx
```

#### A.3 手动导出 ltx（若 deploy 仍无新 ltx）

```bash
source /tools/Xilinx/Vivado/2020.1/settings64.sh
vivado -mode batch <<'EOF'
open_project vivado_project/EdgeAI_ZU4EV.xpr
open_run impl_1
write_debug_probes -force -file deploy/cifar10_accel.ltx
exit
EOF
```

#### A.4 同源验收

```bash
md5sum deploy/cifar10_accel.bit deploy/cifar10_accel.ltx
stat -c '%y %n' deploy/cifar10_accel.bit deploy/cifar10_accel.ltx
# 两者日期应同为本轮 impl 当天；ltx 大小通常 ≠ 5582 B（旧文件）
```

Windows：`E:\WSL_ENV\project\EdgeAI-ZU4EV_Claude\deploy\cifar10_accel.{bit,ltx}`

---

### 阶段 B：Windows Vivado Hardware Manager 连板（约 15 分钟）

#### B.1 启动 Vivado

- 开始菜单 → **Vivado 2020.1** → **Vivado HLx**
- 若仅 WSL 有 Vivado：需 Windows 安装同版本，或用 usbipd 将 JTAG 透传到 WSL

#### B.2 打开 Hardware Manager

1. **Flow Navigator** → **Open Hardware Manager**
2. **Open target** → **Auto Connect**
3. 应看到 `xilinx/zynqmp` / `xczu4ev`

#### B.3 Program bit + probes（JTAG，勿用 fpga_manager 代替）

1. 右键设备 → **Program Device**
2. **Bitstream**: `E:\WSL_ENV\project\EdgeAI-ZU4EV_Claude\deploy\cifar10_accel.bit`
3. **Debug probes**: `E:\WSL_ENV\project\EdgeAI-ZU4EV_Claude\deploy\cifar10_accel.ltx`
4. **Program**

期望：出现 **hw_ila_1**（或类似 ILA 核）。

#### B.4 配置 ILA

| 设置项 | 建议值 |
|--------|--------|
| Capture depth | ≥ 4096 |
| Trigger position | 512 |
| 探针 | `output_stream_TVALID`、`TREADY`、`TDATA[31:0]`、`TLAST` |
| 触发 | `TVALID==1` 且 `TREADY==1`（可先仅 `TVALID` 简化） |

点击 **Run Trigger / Arm**，状态为 **Waiting for trigger**。

> 探针列表无 `output_stream_*` → 回到阶段 A 扩展 `add_dma_ila.tcl` 后重编。

---

### 阶段 C：WSL 触发推理（ILA Armed 后）

```bash
# 在仓库根目录
conda activate <your-env>
bash scripts/board_safe_verify.sh
```

或仅 sample 0（PL 已为 operating 时）：

```bash
scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  scripts/board_fetch_gap.py scripts/dma_infer_common.py scripts/slot32_layout.py \
  deploy/cifar10_bench.npz root@${BOARD_IP}:/tmp/edgeai_bench/

ssh -o ConnectTimeout=8 -o StrictHostKeyChecking=no \
  -o UserKnownHostsFile=/dev/null root@${BOARD_IP} \
  'cd /tmp/edgeai_bench && OUT_DIM=24 OUT_BYTES=96 OUT_LAYOUT=gap_ps \
   OUT_FIXED_SCALE=1024 OUTPUT_PACK_MODE=serial SAMPLE_IDX=0 \
   python3 -u board_fetch_gap.py'
```

回到 Vivado：ILA 应 **Triggered**。

---

### 阶段 D：判读波形

#### 探针信号（优先）

| 信号 | 说明 |
|------|------|
| `cifar10_accel_0/output_stream_TDATA[31:0]` | 输出 beat 数据 |
| `cifar10_accel_0/output_stream_TVALID` | 有效 |
| `cifar10_accel_0/output_stream_TREADY` | DMA 反压 |
| `cifar10_accel_0/output_stream_TLAST` | 帧结束 |
| `axi_dma_0/S_AXIS_S2MM_TDATA` | S2MM 入口（可选） |

#### 判定表（sample 0）

| 情形 | 含义 | 下一步 |
|------|------|--------|
| 连续 24 拍，`TDATA[15:0]` 与 csim 一致 | PL 输出正确 | 查 S2MM / DRAM 解码 |
| 24 拍但数值全错 | bit/IP/权重版本问题 | 核对 bit MD5、HLS IP |
| 拍间有间隔或 0 拍 | slot 空洞在 PL 或 DMA | 查 S2MM、`S2MM_LEN=96` |
| 不足 24 拍 | TLAST 过早或 DMA 未收满 | 查 TLAST 与 `OUT_BYTES` |

#### csim 参考（sample 0，24 拍十六进制）

来源：`notebooks/hls4ml_prj/tb_data/csim_axis_beats.log` 第 1 行

```
3ac 334 2c4 68e 2c0 2af 503 975 352 349 5cb 10a 600 192 2b1 17f 2f3 314 1c3 3ec 506 2a3 4a5 9e
```

| 拍 | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 | 16 | 17 | 18 | 19 | 20 | 21 | 22 | 23 |
|----|---|---|---|---|---|---|---|---|---|---|----|----|----|----|----|----|----|----|----|----|----|----|----|
| hex | 3ac | 334 | 2c4 | 68e | 2c0 | 2af | 503 | 975 | 352 | 349 | 5cb | 10a | 600 | 192 | 2b1 | 17f | 2f3 | 314 | 1c3 | 3ec | 506 | 2a3 | 4a5 | 9e |

板端 DRAM 当前（错误，十进制 int16）：`511, 1708, 0, 0, 1019, 1437, ...`

#### 若 ILA 为 serial 24 拍但 DRAM 有空洞

重点查 **axi_dma_0 S2MM** 与 `output_stream` 之间是否有 dwidth converter，以及 `S2MM_LEN` 是否为 96（`OUT_BYTES`）。

#### 导出波形（可选）

Vivado ILA → **Export Waveform** → `results/ila_capture_sample0.csv`

---

### 阶段 E：常见问题

| 现象 | 处理 |
|------|------|
| SSH 超时 | 断电重启板子；先 `board_load_only`，再 devmem |
| Hardware Manager 无设备 | 检查 JTAG USB、驱动、关闭其他 Vivado |
| 无 hw_ila | bit 无 debug hub → 重做阶段 A |
| Program 后行为异常 | ILA 会话以 **JTAG 烧录的 bit+ltx** 为准，与 fpga_manager 加载可能不一致 |
| ILA 不触发 | 简化触发为仅 `TVALID`；确认 WSL 推理命令成功 |

---

## 执行 Checklist

```
[ ] 0  Windows: ping ${BOARD_IP} + JTAG 接好
[ ] 0  WSL: ssh 登录板子，fpga0 == operating（否则 board_load_only）
[ ] A  bit 与 ltx **同日同源**（当前 ltx 为 5/26 过期 → 必须重编+write_debug_probes）
[ ] B  Windows Vivado: Program **配对**的 bit + ltx（勿用旧 ltx）
[ ] B  配置 ILA 触发，Arm
[ ] C  WSL: board_safe_verify 或 board_fetch_gap sample 0
[ ] D  对比 24 拍 vs csim_axis_beats.log 第 1 行
[ ] D  记录结论：PL 对 / S2MM 错 / 仍 slot 空洞
```

---

## 相关文件

| 文件 | 用途 |
|------|------|
| `scripts/board_safe_verify.sh` | 安全上板（PL reload + 单次 fetch） |
| `scripts/board_fetch_gap.py` | 板上单次 DMA 推理 |
| `tcl/add_dma_ila.tcl` | 向 BD 添加 ILA（需扩展 output_stream 探针） |
| `tcl/ila_program_and_arm.tcl` | JTAG 烧录 + 自动 arm（WSL + JTAG 时） |
| `results/mm2s_csim_board_align.json` | MM2S 对比报告 |
| `.cursor/skills/board-devmem-safe/SKILL.md` | 板端 devmem 硬性守则 |
