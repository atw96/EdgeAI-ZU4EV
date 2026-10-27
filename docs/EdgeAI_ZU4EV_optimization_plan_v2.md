# EdgeAI-ZU4EV 优化方案 v2（交给本地 agent）

> 日期 2026-10-17。输入：`progress_for_claude_optimization.md`（任务书 v1）、hls4ml 1.3.0 源码（pip wheel 实读）、近期文献。
> 配套脚本：`rf_planner.py`（合法 RF 枚举 + 并行度均衡分配，已在 hls4ml 1.3.0 规则下自测）。
> 标记约定：**[源码]** 已对照 hls4ml 1.3.0 源码核对；**[文献]** 来自公开文献；**[推断]** 由数字推出、必须实测；**[待验]** 未验证的假设。
> 未能访问你的仓库、板子和 Vivado HLS 2020.1，凡涉及它们的行为一律是 [推断]/[待验]。

---

## 0. 结论（先读这一页）

1. **数值链已闭合，同意任务书。** 精度不是当前瓶颈，延迟才是。
2. **57.43 ms 不能用「只有 24 个并行乘法器」解释。** 按任务书自己的周期模型，当前配置的下限是：层间不重叠 Σ(输出像素×RF)=1 267 200 拍=6.34 ms，层间完全重叠 max=589 824 拍=2.95 ms（200 MHz）。实测比它大 9～19 倍。
3. **一个值得立刻查的数字关系 [推断]：**
   `9 × 1 267 200 拍 / 200 MHz + 0.40 ms(PS侧下限) = 57.42 ms`，实测 57.43 ms（σ=0.02 ms）。
   误差约 0.02%，且只用了一个自然整数 9。它指向两个叠加的结构性问题：**(a) 每个输出像素的代价是 RF 的约 9 倍；(b) 六层表现为串行累加而不是 dataflow 重叠。** 两者都是 HLS 实现问题，不是硅片不够。
4. **任务书里的 A1/A2 RF 表有 6 处在 hls4ml 里非法 [源码]**：hls4ml 只检查「RF 整除权重数」不够，还要求 `RF<n_in 时 RF|n_in`，`RF≥n_in 时 RF 是 n_in 的倍数`。非法值会被**静默改写**成最近合法值（只打印一行 WARNING），实验会被错误归因。合法表见 §5。
5. **先做 A1'：`RF = n_in`（P = n_out，共 120 个乘法器）。** 这一步同时把 RF 落到 `rf_leq_nin` 分支（见 §3 的 H1），是区分各假设最便宜的实验。预测见 §4。
6. **硅片包络 [推断]：** 5.07 M MAC，700 个乘法器按 MAC 比例均衡、完全重叠时约 7.2k 拍≈36 µs。现实能到 0.1～0.2 ms 量级。任务书里「A2 有机会 <10 ms」的预期过于保守，57 ms 是实现问题不是器件上限。
7. **精度线（B）与降 RF 线分开做。** 先 Q6→Q8（预期上限约 +2 点，只能追回到 FP32 的 81%），再加宽；全部用 10 000 张测试集 + 配对检验（McNemar），不要再用 N=100。
8. **文献取舍：** 采用 hls4ml 自身的 FIFO 深度优化、ReLU 合并这类已验证手段；DA(da4ml)、Fused、逻辑门网络对本网络/本器件不适用；FINN 与 FracBNN 作为「换架构」的对照轨道（§9），不进入主线。

---

## 1. 对任务书 v1 的审查

| # | 任务书的说法 | 判断 | 依据 / 动作 |
|---|---|---|---|
| 1 | 数值路径闭合（csim=板端=82%） | 同意 | 保留。但 N=100 的 SE≈3.8 点，所有新增结论按 §7 重测 |
| 2 | 57 ms 的主因是 24 个乘法器，A1 约 15～25 ms | **不成立 [推断]** | 周期模型下限 2.95/6.34 ms，与 57.43 ms 差 9～19×。先做 §3 阶段 0 的诊断，再谈收益 |
| 3 | 新 RF 只需整除权重数 | **不充分 [源码]** | `fpga_backend.py::_validate_reuse_factor`，见 §5.1。A1: conv2a=180、conv2b=225、conv3a=270、conv3b=324 非法；A2: conv2a=60、conv2b=75 非法 |
| 4 | 每层 P=16/48 的统一档位 | **不可表示 [源码]** | n_out=20/24 的层，P 只能取 n_out 的约数，或 n_out×(n_in 的约数)。统一 P=16 对 conv2/conv3 做不到 |
| 5 | `BramFactor` 改小是「面积形态实验」 | 同意 | 只在需要把权重放进 BRAM 时再做，与延迟实验分开 |
| 6 | 若 DSP≈0，用 `bind_op` 绑 DSP48 | **需改口径 [待验]** | `bind_op` 属于 Vitis HLS 的 pragma；Vivado HLS 2020.1 用 `RESOURCE core=...`，以 UG902(2020.1) 为准。**6-bit×6-bit 乘法落到 LUT 本来就合理**，真正红线是 LUT<60k 与时序，不是 DSP 数 |
| 7 | URAM 为 0 | **需复核** | 公开器件目录列出 XCZU4EV 有 48 个 UltraRAM 与 128 个 BRAM36（来源见 §8）。以实现后 `report_utilization` 的 URAM 行为准，别沿用 HLS 报告里的 0 |
| 8 | A2「<10 ms」 | 过保守 | 见结论 6 |
| 9 | 精度对比用 bench N=100 | 不够 | 用同一批 10 000 张保存逐样本对错数组，做配对检验，见 §7 |
| 10 | Dense 留在 PS、不动协议 | 同意 | 保持 96 B / scale 1024 / serial；宽网时 `OUT_BYTES=OUT_DIM×4` |

---

## 2. 文献与工具链进展（只列与决策相关的）

| 来源 | 要点 | 与本项目的关系 | 采纳 |
|---|---|---|---|
| hls4ml 1.2.0（2025-11）/ 1.3.0（2026-03-20）发布说明、文档 | 1.2 加入 Distributed Arithmetic、HGQ2、Keras v3 前端；1.1 加入 Vitis 后端 FIFO 深度优化器；1.3 文档列出 Fused、DA、FIFO 优化等高级特性。io_stream 卷积有 LineBuffer（默认）与 Encoded 两类实现，`ParallelizationFactor` 只对 io_parallel 有效 | 本项目是 io_stream+Resource，**调并行度的唯一旋钮是每层 RF**；`ConvImplementation` 可做 A/B | 部分（§6） |
| hls4ml 文档「Fused Strategy」 | 只对 **Dense 链 + io_parallel + Vitis** 有效，conv 层会退回 Resource | 不适用 | 否 |
| hls4ml 文档 + da4ml 论文 (arXiv 2507.04535, 2026-03 刊出) | DA 把常数矩阵向量乘变成加法图，相对 Latency 策略最多省约 30% LUT 并去掉全部 DSP；**要求被展开的 CMVM 的 RF=1** | 本网络 18 720 个卷积权重全展开远超 ZU4EV 的 LUT 预算 [推断]；只对很小的层可能有用，而瓶颈层 conv1b 恰好最大 | 否（备注即可） |
| hls4ml PR #800（已并入 0.8.0）| 报告 line-buffer + io_stream + Resource + RF>1 的卷积，因 `inline` 导致延迟差 3×～近 20×，去掉 inline 后恢复 | 与「实测远慢于周期模型」同类现象；你们的 AXI/stream 补丁可能改动过卷积函数 | 作为 H3 检查项 |
| Borras 等, *Open-source FPGA-ML codesign for the MLPerf Tiny Benchmark* (arXiv 2206.11791) | hls4ml 的 CIFAR-10 模型（58 115 参数，8–12 bit，83.5%）在 Pynq-Z2 上 27.3 ms、4 个 DSP、LUT 53.7%；FINN CNV-W1A1（二值，84.5%）1.5 ms、0 DSP、LUT 46.1%。论文指出 hls4ml 版本的延迟主要耗在一个卷积层，并计划改进流水；同文给出 **FIFO 深度优化**与 **ReLU 合并**使 HLS 估计的 BRAM 从 477 降到 146 | 与你们的现象同构：hls4ml+io_stream+Resource 天生慢，延迟集中在单层。FIFO 优化/ReLU 合并是已被验证的省面积手段 | 采用 FIFO 优化、ReLU 合并（§6） |
| FINN v1.0.0-alpha（Vivado 2024.2 为默认流）、FINN PR #1650（2026-07，为 CNV 等示例在 ZCU102/ZCU104 等板卡建回归） | FINN 仍在活跃维护，CNV(W1A1/W1A2/W2A2) 是官方示例；但**要求 Vitis HLS 系工具链（≥2022.2）**，与你们的 Vivado HLS 2020.1 不兼容 | 「换架构」对照轨道需要新装工具链 | 仅 §9 |
| Zhang 等, FracBNN (FPGA'21) 与官方代码库 | CIFAR-10 精度 89.1%，在 Ultra96-v2(ZU3EG) 上整网展开，2806.9 FPS，LUT 72.9%；官方 HLS 代码走 Vivado HLS 流程；权重 1 bit、激活约 1.4 bit | **同系列小一号的器件（ZU3EG）已证明 ~0.36 ms、89%**，说明 ZU4EV 上 82%/57 ms 离器件包络很远 | 作为对照与目标参照（§9） |
| Petersen 等, 卷积可微逻辑门网络 (NeurIPS 2024)；BitLogic (arXiv 2602.07400) | CIFAR-10 86.29% 需要 6100 万逻辑门；BitLogic 在 <0.3 M 门下 72.3% | ZU4EV 仅 87 840 个 LUT，能装下的规模对应的精度远低于你们的 82% [推断] | 否 |
| Xilinx WP486、arXiv 2203.11028 (DSP-Packing) | DSP48E2 可在共享一个操作数时一次做两个 INT8 乘法 | 需要手写 RTL/自定义乘加核，hls4ml 里没有 | 否（未来轨道） |
| arXiv 2412.20974（Vitis AI，ZCU104，CIFAR-10） | DPU 路线单线程 584 FPS、2 线程 1021 FPS | 只作为「厂商 DPU」基线量级参照 | 否 |

---

## 3. 阶段 0：诊断（不改设计，不改位宽）

目的：在花一次 Vivado 实现时间之前，把「57 ms 到底花在哪」定位出来。每条都有明确的判据。

### 3.1 假设表

| 编号 | 假设 | 为什么怀疑 | 判据 |
|---|---|---|---|
| H1 | **RF>n_in 的分支（`dense_resource_rf_gt_nin_rem0`）里 `IndexLoop` 没被流水化，每次迭代含取模，约 8 拍/迭代，叠在 `ReuseLoop` 的 1 拍/迭代上，合计≈9×RF** [源码+推断] | 当前六层 RF 全是 n_in 的 4～6 倍，全都落在这个分支；该分支在 `ReuseLoop` 之前有一个 RF 次迭代、内含 `(ir+1)%nin` 的 `IndexLoop`，源码里没有给它加 PIPELINE。分支选择见 `nnet_dense_resource.h::dense_resource`：`RF<=n_in`→`rf_leq_nin`（无 IndexLoop），`RF%n_in==0`→`rf_gt_nin_rem0`，其余→`rf_gt_nin` | csynth 的 loop 子表里 `IndexLoop` 的 Iteration Latency 与是否流水；每层 Latency 是否≈`px×RF×9` |
| H2 | **六层没有重叠，等于 dataflow 丢失或被串行化**（你们的 AXI/stream 补丁可能动过顶层） | 实测对应「Σ 各层」而不是「max 各层」；`hls_ip_latency.json` 里 II 最大 2.67e6 拍与「一帧算完才能下一帧」一致 | 生成的顶层 `.cpp` 里是否仍有 `#pragma HLS DATAFLOW`；csynth 报告的 Pipeline type；RTL cosim 两帧的 interval 是否≈latency |
| H3 | 卷积函数里有会拖慢流水的 `inline`/pragma 差异（见 hls4ml PR #800 现象） | 补丁流程改过 `firmware/nnet_utils` 的可能性 | `diff -r` 你们工程里的 `firmware/nnet_utils` 与已安装 hls4ml 1.3.0 模板 |
| H4 | PL 时钟实际不是 200 MHz | 若是 100 MHz，同样的周期数对应 2× 的时间，则 9× 的系数会变成 4.5× | 板上读 PL 时钟 + `.hwh` 里 `FREQ_HZ` + Vivado timing summary |
| H5 | 上述 9.06 倍关系只是巧合 | 概率约 0.3% 量级，但不为零 | 上面四项全否定时才采纳 |

### 3.2 要做的事（按顺序，全部只读/只仿真）

```bash
# P0.1 时钟（板上，确认 fpga0=operating 之后）
grep -o 'FREQ_HZ[^/]*' <bit对应的>.hwh | sort | uniq -c
cat /sys/kernel/debug/clk/pl0_ref/clk_rate      # 若 debugfs 里没有这一项，换用 clk_summary 里对应的 pl0 行

# P0.2 在 edgeai_hls4ml13 环境里确认 RF 合法性规则与你们当前配置
python3 rf_planner.py --crosscheck               # 与 hls4ml 自带 get_valid_reuse_factors 完全一致才继续
# 在上一次 convert 日志里 grep：
grep -n "Invalid ReuseFactor" <convert日志>      # 若有，说明历史实验用的不是你以为的 RF

# P0.3 补丁是否动过卷积/稠密核
diff -r "$(python3 -c 'import hls4ml,os;print(os.path.dirname(hls4ml.__file__))')/templates/vivado/nnet_utils" \
        <hls工程>/firmware/nnet_utils
grep -n "DATAFLOW" <hls工程>/firmware/*.cpp

# P0.4 对【当前】RF 配置重新 csynth，读每个实例/循环的数
#   需要：每层 Latency、IndexLoop / ReuseLoop 的 Trip count、Iteration Latency、是否 pipelined
#   然后与理论值对照： layer_cycles ≈ out_pixels * RF * (1 + c)，求 c
```

产出：`results/p0_diag.json`，字段至少有 `pl_clock_hz`、每层 `csynth_latency_cycles`、`theory_px_x_rf`、`ratio`、`has_dataflow`、`indexloop_iter_latency`、`diff_nnet_utils_empty(bool)`。

### 3.3 阶段 0 的出口

- 若 `ratio≈9` 且 IndexLoop 的 Iteration Latency≈8 且未流水 → H1 成立，进入阶段 1。
- 若 csynth 报告顶层不是 dataflow 或 interval≈latency → H2 成立，**先修顶层 dataflow**（单独一次提交，不改 RF），再进入阶段 1。
- 若 H4 成立 → 先把时钟问题解决（是时钟树/约束问题，不是 HLS 问题）。
- 若全部否定 → 停，把 `p0_diag.json` 发回给我再讨论，不要继续降 RF。

---

## 4. 阶段 1：A1'（`RF = n_in`，P = n_out）

### 4.1 改动（只改 `scripts/v19_hls_config_common.py`）

```python
RF_PER_LAYER = {
    'conv1a': 27, 'conv1b': 144, 'conv2a': 144,
    'conv2b': 180, 'conv3a': 180, 'conv3b': 216,
    'predictions': 240,           # 不在 PL 里，保持
}
cfg['Model']['ReuseFactor'] = 27  # 取各层最小值
# 加护栏：
from rf_planner import valid_rf
# conv 的 n_in = Cin*9, n_out = Cout；断言每层 RF 合法，否则直接 raise
```

这六个 RF 全部 `RF == n_in`，落在 `rf_leq_nin` 分支，没有 IndexLoop。位宽与 h5 不动。

### 4.2 预期（理想周期模型，不含流水线填充、FIFO、AXIS 适配等开销，以 csynth/cosim 为准）

| 项 | 数值 |
|---|---|
| 六层并行乘法器合计 ΣP | 120（当前 24） |
| 各层周期 px×RF | 27 648 / 147 456 / 36 864 / 46 080 / 11 520 / 13 824 |
| Σ（不重叠） | 283 392 拍 = 1.42 ms |
| max（完全重叠） | 147 456 拍 = 0.74 ms（conv1b） |

对板端 `reset_each` 延迟的分情形预测（PS 侧下限按 0.40 ms 计）：

| 阶段 0 的结论 | A1' 预测板端延迟 |
|---|---|
| H1 成立 + 六层仍串行 | ≈ 1.42 + 0.40 ≈ **1.8 ms** |
| H1 成立 + dataflow 已修复 | ≈ 0.74 + 0.40 ≈ **1.1 ms** |
| 「9×」是所有 dense 调用固有的（H1 不成立） | ≈ 9×1.42 + 0.40 ≈ **13.2 ms**；此时去看阶段 3 的 3c |

### 4.3 验收门（任一不过就回退，不进入阶段 2）

1. csynth 日志里**没有** `Invalid ReuseFactor`。
2. csim 对同一批 1000 张图：GAP 输出与 P=4 版本**逐比特一致**。`bit_exact=True` 且累加器位宽充足时，RF 只改变调度，不应改变整数结果。有差异就先查 accum 位宽，不要继续。
3. 实现后：LUT<60 000，DSP<500，BRAM_18K<160，200 MHz 下 WNS≥0；利用率写入新 JSON，不覆盖旧报告。
4. 板端：`FORCE_PL_RELOAD=1`，HP0 64-bit，0xAA 洞为空，N=1000 的延迟中位数/p99，`reset_each` 与 `no_reset` 各一组。
5. 精度：10 000 张测试集 Top-1 与当前 Phase-0 基线相差 ≤0.5 点（理论上应为 0）。

**回退：** 恢复 `RF_PER_LAYER` 旧值；板端 bit/hwh MD5 回到 `46987907…` / `7576e1ed…`。

---

## 5. 阶段 2：均衡并行度（合法 RF 表）

### 5.1 合法性规则 [源码，hls4ml 1.3.0 `fpga_backend.py`]

对卷积：`n_in = Cin×3×3`，`n_out = Cout`。RF 合法当且仅当

```
(ceil(n_in*n_out / min(n_in,RF)) % n_out == 0  或  RF >= n_in)
且 (RF % n_in == 0  或  RF < n_in)
且 (n_in*n_out) % RF == 0
```

等价地：**RF 是 n_in 的约数（RF<n_in），或 RF = n_in×d 且 d 整除 n_out。** 非法值由 `set_closest_reuse_factor` 改成最近合法值，只打印 WARNING。

可表示的并行乘法器数 P = n_in×n_out/RF：
- `RF ≤ n_in`：P = n_out × k，k 为 n_in 的约数；
- `RF = n_in×d`：P = n_out/d，d 为 n_out 的约数。

只用 `RF ≤ n_in` 的方案可以避开 H1 的 IndexLoop，**下面的方案全部取这个分支。**

### 5.2 每层可选 RF（当前网络，节选；完整表用 `rf_planner.py` 生成）

| 层 | n_in | n_out | px | `RF≤n_in` 的合法取值（P=n_in·n_out/RF） |
|---|---:|---:|---:|---|
| conv1a | 27 | 16 | 1024 | 27(P16) 9(P48) 3(P144) |
| conv1b | 144 | 16 | 1024 | 144(16) 72(32) 48(48) 36(64) 24(96) 18(128) 16(144) 12(192) 9(256) |
| conv2a | 144 | 20 | 256 | 144(20) 72(40) 48(60) 36(80) 24(120) 16(180) |
| conv2b | 180 | 20 | 256 | 180(20) 90(40) 60(60) 45(80) 36(100) 30(120) |
| conv3a | 180 | 24 | 64 | 180(24) 90(48) 60(72) 45(96) |
| conv3b | 216 | 24 | 64 | 216(24) 108(48) 72(72) 54(96) |

### 5.3 推荐的三档（由 `rf_planner.py` 在「最大层周期最小」准则下算出）

| 档 | conv1a / 1b / 2a / 2b / 3a / 3b 的 RF | 各层 P | ΣP | max 层周期 | 理想单帧(重叠) | Σ 层周期 |
|---|---|---|---:|---:|---:|---:|
| A1'（已在 §4） | 27 / 144 / 144 / 180 / 180 / 216 | 16/16/20/20/24/24 | 120 | 147 456 | 0.74 ms | 283 392 |
| **A2-L** | 27 / 36 / 144 / 90 / 180 / 216 | 16/64/20/40/24/24 | 188 | 36 864 | 0.18 ms | 149 760 |
| **A2-M** | 9 / 18 / 72 / 60 / 180 / 216 | 48/128/40/60/24/24 | 324 | 18 432 | 0.092 ms | 86 784 |
| **A2-H** | 9 / 12 / 48 / 45 / 180 / 108 | 48/192/60/80/24/48 | 452 | 12 288 | 0.061 ms | 63 744 |

（延迟列是单层 200 MHz 理想值，不含 PS 侧 0.40 ms 与各类填充开销。）

### 5.4 推进规则

1. 一次只推进一档，顺序 A2-L → A2-M → A2-H。
2. **LUT 外推：** 每做完一档，用已有的 (ΣP, LUT) 数据点做线性拟合，预测下一档的 LUT；预测 >60 000 则不跑下一档。6-bit 乘法大概率落在 LUT，别指望 DSP 数线性增长。
3. 停手：板端延迟相对上一档下降 <15%；或任一资源顶到红线（LUT<60k / DSP<500 / BRAM_18K<160 / WNS≥0）；或 csim 与 Keras 差 >1 点。
4. 若 csynth 显示 DSP≈0 且 LUT 增长明显超过线性预测，先排查是否有除法/取模被综合成 LUT（H1 的取模就会这样），再考虑绑 DSP。绑 DSP 用 Vivado HLS 2020.1 支持的 pragma 写法（先做单层微基准验证）。

---

## 6. 阶段 3：结构性修补（只在触发条件满足时做）

| 编号 | 触发条件 | 动作 | 说明 |
|---|---|---|---|
| 3a | 需要用 `RF>n_in`（低并行度、省乘法器）且 H1 成立 | 本地补丁 `nnet_dense_resource.h`：给 `IndexLoop` 加 `#pragma HLS PIPELINE II=1`，或把 `outidx` 改成编译期查表 | 补丁必须进入你们已有的 patch 列表并留档。主线方案不需要它 |
| 3b | 阶段 1/2 的延迟与周期模型仍相差 >3× | `ConvImplementation` 做 `LineBuffer` vs `Encoded` 的 A/B | 文档称 LineBuffer 通常略优，这是低优先级实验 |
| 3c | 「9×」不是 IndexLoop 引起 | 仅对 conv1b 试 `Strategy='Latency'`，`ReuseFactor=R` 作为每输入像素的 II（源码里 `conv_2d_buffer_cl` 在 latency 分支对像素循环 `PIPELINE II=reuse_factor`）；权重进寄存器，conv1b 约 2304×6 bit，面积可接受 | **Latency 策略下 RF 不做合法性检查 [源码]**，P≈n_in·n_out/R 由 HLS 调度决定，要实测 |
| 3d | RF 已定稿后 | hls4ml `fifo_depth_optimization`（需 RTL cosim）；检查 ReLU 合并 pass 是否可用 | MLPerf Tiny 论文里这两项使 BRAM 大幅下降；这是面积优化，不是延迟优化，放在最后 |
| 3e | 以上都做完仍异常 | 评估迁到 Vitis HLS 2023.2/2024.1 | hls4ml 的 Fused 文档称其估计是在 Vitis HLS 2024.1 上测定、2023.2 上复核的，并提示 2025.1 行为不够可预测，可作为选版本的参考。要重做 BD 与板端流程，代价大，最后手段 |

---

## 7. 测量与统计规范（全阶段通用）

1. **精度**：每个变体在同一固定顺序的 10 000 张测试集上评测，保存逐样本对错数组 `correct_<variant>.npy`。
2. **比较两个变体**：用配对检验，不用各自的 Top-1 相减。
   ```python
   from scipy.stats import binomtest
   b = ((a==1)&(c==0)).sum(); cc = ((a==0)&(c==1)).sum()   # 不一致对
   p = binomtest(min(b,cc), b+cc, 0.5).pvalue                # McNemar 精确检验
   ```
3. **四方对齐**：Keras 全模型、GAP+`dense_head.npz`、csim、板端，在同一批样本上差 >1 点就停，先查数值。
4. **延迟**：N≥1000 连续帧，报告中位数、p99、标准差；`reset_each` 与 `no_reset` 各一组；同时记录纯 PS 开销（只读 GAP，不跑 DMA，当前 0.40 ms）。板端 10 000 张在 57 ms/帧下约 9.6 分钟，A1' 之后只需秒级，全量评测不是负担。
5. **结果文件**：每个实验一个 JSON（变体名、RF 表、csynth 每层周期、实现资源、WNS、延迟统计、精度与配对检验 p 值、bit/hwh MD5）。不覆盖旧文件。
6. **PS 侧下限**：当 PL 延迟降到 ~1 ms 以内，0.40 ms 的 PS 侧开销会成为主项。到那时把轮询/解码/Dense 从 Python 挪到 C，或至少预分配缓冲、避免每帧 Python 对象分配；目标 ≤0.1 ms。这项放在 A2 之后做。
7. 若板上有功耗监测手段，记录 PL+PS 功耗并换算 J/帧，与 CPU TFLite（12.23 ms）对比，作品集价值高。

---

## 8. 阶段 5：精度线 B（与降 RF 线严格分开）

前置条件：阶段 2 至少达到板端 ≤2 ms，否则加宽只会让慢的实现更慢。

### 8.1 B1：Q6 → Q8（通道不变）

- 改 `build_q6_input_qact()` 的 `quantized_bits`/`quantized_relu` 位宽（权重、激活、`input_qact` 三处一起），其余不动，微调。
- 期望：只能追回 Q6 相对 FP32 的 1～2 点（79.2% vs 81.2%），**不要期望超过 FP32**。
- 面积：若乘法落在 LUT，8-bit 乘法的 LUT 成本约为 6-bit 的 1.8 倍量级 [推断]，需要按 §5.4 的 LUT 外推重新核。
- 判据：10 000 张上 McNemar 显著（p<0.05）且净增 ≥1 点才算有增益。

### 8.2 B2：加宽（32/32/40/40/48/48）

- MAC 约 ×3.83（19.39 M），权重约 ×3.8。**必须带着已验证的并行度**，用 `rf_planner.py --widen 32,32,40,40,48,48` 重新算合法 RF：

| 预算 | conv1a / 1b / 2a / 2b / 3a / 3b 的 RF | 各层 P | ΣP | max 层周期 |
|---|---|---|---:|---:|
| ΣP≤480 | 27 / 48 / 144 / 180 / 360 / 432 | 32/192/80/80/48/48 | 480 | 49 152（0.25 ms） |
| ΣP≤640 | 27 / 36 / 144 / 120 / 360 / 432 | 32/256/80/120/48/48 | 584 | 36 864（0.18 ms） |

- DSP 红线 500 对应 P≈500，**若乘法落 LUT 则 LUT 红线先到**，所以仍按 §5.4 做外推再跑。
- `OUT_DIM` 变为 48 时，`OUT_BYTES = OUT_DIM×4 = 192`；`dense_head.npz` 形状变为 (48,10)；PS 公式不变。
- **训练建议**（不依赖文献，是标准做法，需实验确认）：宽网从头训、不要只微调 40 epoch；老师现在只有 88.5%，蒸馏上界受限于老师，换一个更强的老师（若有）通常比继续加宽更便宜；保留 EMA；KD 的 α/T 在新网上重扫一次。
- **预期区间 [推断]**：10 000 张上先到 84%～87%，不要写成验收指标。参照：MLPerf Tiny 的 hls4ml CIFAR-10 模型 58k 参数 83.5%；FracBNN 在 ZU3EG 上已到 89.1%（不同网络，只作为包络参照）。

### 8.3 验收（沿用任务书的口径）

全测试集 Top-1；csim 与 Keras 差 ≤1 点；板端与 csim 差 ≤1 点；0xAA 无洞。老师 88.5% 只是上界参考，不是验收线。

---

## 9. 「换架构」对照轨道（主线之外，需要明确批准才做）

| 轨道 | 内容 | 代价 | 触发条件 |
|---|---|---|---|
| C1 FINN CNV-W2A2 或 W1A1 | 在 ZU4EV 上用 FINN+Brevitas 做同板对照，作品集里可以写「hls4ml vs FINN 同一块板」 | 要装 Vitis HLS 系工具链（FINN 当前默认 Vivado 2024.2），与现有 2020.1 工程并存；工作量中到大 | 阶段 2 完成后仍想要 ≥85% 且延迟 <1 ms |
| C2 FracBNN 官方 HLS 复现 | 作为「ZU3EG 都能做到 89.1%/约 0.36 ms」的对照；官方流程基于 Vivado HLS + PYNQ | 要把 PYNQ overlay 接口改成你们的 DMA 协议；二值权重需要重新训练流程 | 目标变为冲 89% 精度 |

默认不做。主线是先把当前网络的延迟降到应有水平，再用同一套并行度扩展到更宽的网络。

---

## 10. 给本地 agent 的约束

1. 一次只改一件事；每一步写「预期 / 失败时如何回退」，并先写预测值再跑，跑完对照。
2. 环境、路径、板端访问顺序、禁止并发 SSH 一律按 `docs/porting_env_hardware_config.md`；未确认 `fpga0=operating` 不碰 `0x66C00000`、`0x80040000`。
3. 板端协议保持 96 B / scale 1024 / serial / OUT_DIM=24（B2 时按 §8.2 改）。不用 `run_v19_qat_resume.sh` 里的 92/256/slot。
4. 不覆盖旧报告；旧报告标注「过时」而不是删除（沿用任务书 §5.2 的清单）。
5. 每个已改动的源码位置就地写注释，说明根因与日期（项目约定）。
6. 对外叙事（简历/面试）可以直接用的主线：*诊断（周期模型 vs 实测，发现 9.06× 关系）→ 源码级定位（RF 合法性、dense_resource 分支）→ 修复并上板（延迟 57 ms → X ms，数值逐比特不变）→ 用配对检验把精度改进量化*。其中 X 以板端实测为准，不要提前写数字。

---

## 附录 A：我在 hls4ml 1.3.0 源码里核对过的点

| 事实 | 位置 |
|---|---|
| RF 合法性规则；非法值只打印 WARNING 并改写 | `backends/fpga/fpga_backend.py` 的 `_validate_reuse_factor`、`set_closest_reuse_factor` |
| 只有 `Resource` 策略才做 RF 合法性修正，`Latency` 不做 | `backends/vivado/vivado_backend.py` 里 `is_resource_strategy` 守卫 |
| Conv2D 的 `n_in=Cin·kh·kw`、`n_out=Cout` | `backends/vivado/passes/convolution_templates.py` |
| `RF≤n_in`→`rf_leq_nin`；`RF%n_in==0`→`rf_gt_nin_rem0`（带 `IndexLoop`，内含 `%`，源码无 PIPELINE）；其余→`rf_gt_nin` | `templates/vivado/nnet_utils/nnet_dense_resource.h` |
| io_stream 的 line-buffer 卷积：`Latency`/DA 才对像素循环加 `PIPELINE II=reuse_factor`；`Resource` 没有 | `templates/vivado/nnet_utils/nnet_conv2d_stream.h` 的 `conv_2d_buffer_cl` |
| `compute_output_buffer_2d` 是 `INLINE OFF`，内部调用 mult_config 的 dense | `templates/vivado/nnet_utils/nnet_conv_stream.h` |
| 'same' 填充由单独插入的 ZeroPadding 节点完成，卷积本身 `assert(pad==0)` | `backends/vivado/passes/conv_same_pad.py` 与 `conv_2d_buffer_cl` |
| 生成的 tcl 里没有 `config_compile -pipeline_loops`（Vivado HLS 是否自动流水化循环需以 csynth 为准） | `templates/vivado/build_prj.tcl` |

## 附录 B：`rf_planner.py` 用法

```bash
python3 rf_planner.py                                  # 当前网络：合法 RF、A1'、三档均衡方案、任务书里非法 RF 的改写结果
python3 rf_planner.py --widen 32,32,40,40,48,48        # 加宽网络的均衡方案
python3 rf_planner.py --crosscheck                     # 在 edgeai_hls4ml13 里与 hls4ml 自带函数逐项比对
```

## 附录 C：来源

- hls4ml 文档与发布说明：https://fastmachinelearning.org/hls4ml/intro/release_notes.html 、/ir/ir.html 、/advanced/fused.html 、/advanced/da.html
- hls4ml PR #800：https://github.com/fastmachinelearning/hls4ml/pull/800
- Borras 等，MLPerf Tiny 的 hls4ml/FINN 工作：https://arxiv.org/abs/2206.11791
- da4ml：https://arxiv.org/abs/2507.04535
- FINN v1.0.0-alpha 发布说明：https://github.com/Xilinx/finn/discussions/1689 ；PR #1650：https://github.com/Xilinx/finn/pull/1650
- FracBNN：https://arxiv.org/abs/2012.12206 ；代码：https://github.com/cornell-zhang/FracBNN
- 卷积可微逻辑门网络：https://arxiv.org/abs/2411.04732 ；BitLogic：https://arxiv.org/abs/2602.07400
- DSP48E2 打包：Xilinx WP486；https://arxiv.org/abs/2203.11028
- Vitis AI / ZCU104 / CIFAR-10：https://arxiv.org/abs/2412.20974
- ACU4EV / XCZU4EV 资源（LUT 87 840、BRAM36 128、URAM 48、DSP 728）：https://boards.fpgadeveloper.com/soms/ACU4EV
