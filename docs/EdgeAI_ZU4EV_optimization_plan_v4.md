# EdgeAI-ZU4EV 优化方案 v4：先闭合数值，再闭合面积与延迟，最后端到端上板

> 依据：2026-10-17 的 P1（数值门禁）与 P2（A1' csynth 归因）结果。v3 里仍然有效的部分（P4 单层微基准、P5 IndexLoop 补丁、前沿表、测量规范）不重复，只在这里指出怎么改。
> 标记：**[反馈]** 你给的数；**[算术]** 用你的数直接算出、可复核；**[源码]** 已对照 hls4ml 1.3.0 / QKeras 0.9.0 源码；**[推断]** 由数字推出，必须实测。
> 配套文件：`e2e_compare.py`（三方比对与延迟统计，已用合成数据测过：逐比特一致时退出码 0，改动一个元素退出码 1）、`rf_planner.py`。
> 说明：我看不到你的仓库、板子和 Vivado HLS 2020.1，所有涉及它们的行为都是 [推断]。

---

## 0. 读数结论

1. **RF 不改变数值，已被证实。** 同一环境、同一 h5、同一脚本转换基线 P4 与 A1'：48 个权重头文件和 `defines.h` 逐字相同，`parameters.h` 只差复用因子与 dense 分支，前 1000 张 GAP 逐比特一致 [反馈]。因此 **v3 把「P1 不过门就停掉所有综合」的规定过严了**：数值问题与 RF/延迟问题互相独立。csynth 类实验可以和数值诊断并行，只有「实现（布局布线）和上板」仍需等数值门禁（见 §1）。
2. **真正的发现是：当前转换的数值与 Keras 差 3.3 个点。** Keras 81.8%，csim 78.5%（同一批前 1000 张），GAP 的 MAE 0.087、最大 1.77 [反馈]。已部署 bit 当年的「csim=板端=82%」是在 N=100 上量的，标准误差约 3.8 点，不能证明部署模型是 82%。**现在最合理的预期是：已部署的 bit 在 1 万张上大概是 78%～79%，不是 82%。** 这要用 §3 的 D1/D3 实测确认，确认前对外不要再写 82%。
3. **「转换前的工程」与「现在的转换」不是同一套数值。** 你们之前记录过转换前 10 样本 P4 csim 与现在最大差 0.2656 [反馈]，而卷积核数值相同、差异只在类型名（`bias3_t` vs `conv1a_bias_t`）。类型命名变了意味着生成器版本或流程变了，类型/舍入/饱和模式可能随之变化。所以**第一优先级是三方比对：Keras、旧工程 csim、新转换 csim**，看是新转换引入了回归，还是旧的也一样。
4. **conv1a 的 9.5× 现在有了精确解释 [算术]：** ReuseLoop 实际 II=8，因为调度器说 `kernel_data` 端口不够；每个填充位置 27×8+12=228 拍，1156 个位置×228 = **263 568 拍，与你报的数字逐拍吻合**。II=8 恰等于 16 个并行通道÷2 个存储端口，这说明 `kernel_data` 没有被完全分块 [推断]。修法是补 `ARRAY_PARTITION complete`，不是调 RF。
5. **BRAM 278 里 232 个是 BN 流的 FIFO，这几乎肯定不是 A1' 的并行度造成的 [推断]：**
   - 48=16 通道×3，60=20 通道×3，**每通道恰好 3 个 BRAM18**，而 ⌈41/18⌉=3。也就是说开销取决于**元素位宽 41/42 bit**，与深度（16/32）无关。
   - 基线实现后总 BRAM 只有 26 [v1 记录]。同一个网络、同样的 BN 层，基线不可能有 232 个 FIFO BRAM。**最合理的解释是：基线 bit 是用另一套转换（窄 BN 类型）出的，而现在这套转换（hls4ml 1.3.0 + bit_exact）把 BN 输出保持成 41/42 bit。**
   - 这条推论的检验极便宜：对当前转换下的基线 P4 跑一次 csynth（v3 的 P2b）。如果基线 P4 在新转换下也是 BRAM≈270、LUT≈90k，那么面积爆炸是转换流程的问题，**与 RF 无关，A1' 的面积也许根本不是问题**。
6. **所以现在有三个互相独立的问题：数值差 3.3 点（G1）、面积（G2）、延迟（G3）。** 它们都指向同一件事：**新转换流程与已部署 bit 的差别**。先把这个差别量化清楚，再动其他。

---

## 1. 对 v3 的修正

| v3 的规定/判断 | 修正 |
|---|---|
| P1 不过门，P2 之后的综合全部停 | 改为：**csynth 类实验允许并行**（数值与 RF 无关已证实）。**实现、上板、替换 bit 仍须等 G1 通过。** |
| P2b（基线 csynth）排在后面 | 提到第一天，和三方比对同时做，它是判断「面积是不是转换流程造成」的决定性实验 |
| B1 关闭 | 只在 Keras 域关闭。**硬件域未测**：若 3.3 点差距来自舍入/截断，Q8 在硬件域可能表现不同。等 G1 闭合后，用同一固定流程对 Q6 与 Q8 各做一次 csim（1 万张）即可，成本很低，见 §10 |
| 「9×」是 IndexLoop | conv1a 已解释为端口限制（II=8），与 IndexLoop 无关。基线五层的 9× 仍需 P5 检验，两件事分开处理 |
| 精度写 82% | 暂停使用，待 §3 D1/D3 重测 |

---

## 2. 假设体系（更新）

| 编号 | 假设 | 现有证据 | 判据 |
|---|---|---|---|
| HC | 新转换流程（hls4ml 1.3.0 + bit_exact）相对已部署 bit 改变了类型/舍入/饱和 | 类型名变化；旧/新 csim 差 0.2656；BRAM 26 vs 278 | D5 的类型对照表；D2 的基线 csynth |
| HN1 | 舍入模式不一致造成系统性偏差 | QKeras 用 `tf.round`（四舍六入五成双）[源码]；hls4ml 的层输出舍入默认交给编译器（`output_rounding_saturation_mode` 默认关闭，模式为 None）[源码]；bit_exact 流程里对舍入只接受 TRN/RND [源码] | 逐层对照，看有符号均值偏差是否≈−0.5 LSB |
| HN2 | 饱和/回绕不一致（`AP_WRAP` vs `AP_SAT`）造成偶发大误差 | 最大误差 1.77 远大于 MAE 0.087，像偶发事件 | 看误差的重尾分布，定位到具体层/通道 |
| HN3 | 输入量化路径不一致（csim 喂的数据与 Keras 的 `input_qact` 输出不同） | 未验证 | 把 Keras `input_qact` 的输出直接喂给 csim |
| HN4 | BN 常数精度/融合差异 | 缩放系数仅 ~1e-8 差，说明常数本身基本精确，嫌疑较低 | BN 输出处逐层对照 |
| HN5 | PS 端 `dense_head.npz` 与模型最后一层不匹配 | 只影响 Top-1，不影响 GAP MAE | 用 Keras GAP→Dense 与 `dense_head.npz` 对比 |
| HL1 | conv1a 的 `kernel_data` 没有完全分块，ReuseLoop II=8 | 228=27×8+12，1156×228=263 568 [算术] | 补分块后 csynth 看 II |
| HL2 | 基线 57 ms 来自 `rf_gt_nin_rem0` 的 IndexLoop | 未验证（A1' 没覆盖该分支） | v3 的 P5 |
| HA | 面积由 41/42 bit 的 BN 流与宽 BN 乘法决定，而非卷积并行度 | 每通道 3 BRAM；conv 模块仅 ~29k LUT | D2 + §5 |

---

## 3. 第一天：六项并行的低成本诊断（D1–D6）

全部不触碰已部署 bit 与 Q6 权重，结果写 `results/opt_v2/v4_d*.json`。

### D1. 三方数值比对（最优先）

对**同一批测试集前 1000 张**（固定顺序）得到三份输出：

| 来源 | 说明 |
|---|---|
| Keras | 全模型逐层输出（保存每个 QActivation/池化/GAP 的输出） |
| 旧工程 csim | 你说的「转换前那份工程」（产出已部署 bit 的那次）；若能编译就直接跑 |
| 新转换 csim | 当前 P4/A1'（二者已证实一致，只需一份） |

输出表：三者两两的 GAP MAE/最大值、Top-1、配对检验。**判读：**

| 结果 | 含义 | 下一步 |
|---|---|---|
| 旧 csim ≈ Keras，新 csim 差 3.3 点 | 新转换引入回归 | 找出新旧类型差异并还原（§4.3），已部署 bit 其实是好的 |
| 旧 csim ≈ 新 csim，都比 Keras 低 | 回归不存在，部署 bit 一直有这 3.3 点缺口 | 同样要做 §4，并**修正对外精度数字** |
| 旧 csim 优于新、也低于 Keras | 两层问题叠加 | 先还原到旧水平，再追剩余缺口 |

### D2. 基线 P4 在新转换下重跑 csynth（v3 的 P2b，提前）

与 A1' 同一个转换、只改回基线 `RF_PER_LAYER`。记录逐实例的 Latency、LUT、FF、DSP、BRAM_18K，以及各 stream 的位宽/深度/实现。对照：

- 若基线在新转换下 BRAM 也 ≈270：**面积是转换流程问题（HA 成立）**，A1' 的面积爆炸多数不归因于 RF。
- 若基线 BRAM 只有几十：面积确实随并行度变，回头查 §5 的其他项。
- 同时用这一点与板端 57.43 ms 配对，得到 `r = 板端/csynth`。

### D3. 1 万张 csim（新转换），得到「部署模型」的真实精度

1000 张的标准误差约 1.3 点，不够。1 万张 csim 的标准误差约 0.4 点。用同一固定顺序，保存逐样本预测与 GAP（int16/int32 按你现有协议）。再对旧工程做同样的 1 万张（若能编译）。这两个数就是「Keras 与硬件的真实差距」。

### D4. 把 `ReuseLoop II=8` 的原因查实

从 A1' 的 csynth 日志取出 conv1a 的完整消息（数组名、端口数、建议）。再查 conv1b…conv3b 的 `ReuseLoop` 的 achieved II：**若它们都是 1，需要回答为什么只有 conv1a 异常**（它的 n_chan=3、窗口 27 个元素、`block_factor`=16）。同时 grep 生成的 `nnet_conv_stream.h`/`nnet_dense_resource.h` 中 `ARRAY_PARTITION variable=kernel_data` 与 `ARRAY_PARTITION variable=data` 是否在、有没有被补丁删除。

### D5. 旧/新转换的类型对照表

逐层列出旧工程与新工程的：权重/偏置类型、累加器类型、层输出类型（含 `AP_RND/AP_TRN`、`AP_SAT/AP_WRAP`）、BN 的 scale/bias/result 类型、每条 stream 的元素类型与位宽、输入类型。可以直接对 `defines.h` 与 `parameters.h` 做 `diff`，再手工整理成表。记录两边 hls4ml、QKeras、TensorFlow 的版本号与转换参数（尤其 `bit_exact` 与 `Precision` 配置）。

### D6. Keras 侧自检

在**同一个 h5** 上确认三件事：(a) `input_qact` 的输出是否精确落在 6 bit 网格上；(b) Keras 版 GAP→Dense 的 Top-1 与 `dense_head.npz` 做的 Top-1 是否一致（排除 HN5）；(c) 同一批 1000 张上 Keras Top-1=81.8% 能被复现（排除评测路径差异）。

---

## 4. G1：数值闭环

### 4.1 门（替代 v3 §P1 的门）

| 项 | 门 |
|---|---|
| csim vs Keras：GAP MAE | ≤0.03（部署 bit 当年的量级是 0.026） |
| csim vs Keras：Top-1（1 万张）| 差 ≤0.5 点 |
| csim 内部：P4 与 A1' | 逐比特一致（已满足） |
| 极端输入（全黑、全白、棋盘、单通道饱和）| csim 与 Keras 的 GAP 差 ≤1 LSB，无符号翻转 |

### 4.2 二分定位：逐层对照

用 hls4ml 自带的 trace 机制，逐个边界比较 Keras 与 csim。下面是骨架（**未在你的环境运行**，API 名称以你安装的 1.3.0 为准；如果 io_stream 的某层不支持 trace，就另建一个仅用于数值比对的 io_parallel 小工程，两者算术相同）：

```python
import numpy as np, hls4ml
from hls4ml.model.profiling import get_ymodel_keras

cfg = hls4ml.utils.config_from_keras_model(model, granularity='name')   # 你现有的配置照搬
for name in cfg['LayerName']:
    cfg['LayerName'][name]['Trace'] = True
hls_model = hls4ml.converters.convert_from_keras_model(model, hls_config=cfg, ...)  # 其余参数与现有一致
hls_model.compile()
X = x_test[:256]
y_hls, trace = hls_model.trace(X)          # dict: 层名 -> 输出数组
ykeras = get_ymodel_keras(model, X)         # dict: 层名 -> 输出数组
```

只比较两边**都存在的边界**（hls4ml 会合并/改名层）：`input_qact` 之后、每个 `relu`（QActivation）之后、每个池化之后、GAP 之后。每个边界输出下表：

| 指标 | 含义 |
|---|---|
| `max_abs_lsb` | 最大绝对差，以该边界输出类型的 LSB 为单位 |
| `mean_signed_lsb` | 有符号均值差（hls−keras）。**≈−0.5 且比例很高 ⇒ 截断 vs 四舍五入** |
| `frac_ge1lsb`、`frac_ge2lsb` | 差≥1/2 LSB 的元素比例 |
| `first_bad_boundary` | 第一个超过容差（比如 frac_ge1lsb>0.1%）的边界 |

**判读表：**

| 现象 | 根因 | 修法 |
|---|---|---|
| 第一个出问题的边界是 `input_qact` | HN3，输入路径 | 把输入量化直接固化到数据准备（喂整数网格值），并让 hls4ml 输入类型与 `input_qact` 同位宽、同舍入、同饱和 |
| 差值呈 −0.5 LSB 偏置、比例很高 | HN1，TRN vs 四舍五入 | 配 `output_rounding_saturation_mode`（见下） |
| 差值对称、比例很低（只在整数边界） | RND（半入）vs RND_CONV（五成双）的并列项差异 | 见 §4.4 |
| 偶发超大差（几十个 LSB）| HN2，WRAP vs SAT | 对 relu 输出与累加器设 `AP_SAT`；检查累加器位宽 |
| BN 边界处差 | HN4 | 对 BN 的 scale/bias/result 显式给精度，逐层检查 |
| 各边界都对，只有 Top-1 差 | HN5，PS 头不匹配 | 用 Keras 最后一层权重重导 `dense_head.npz` |

### 4.3 修法菜单（按风险从低到高，一次只做一项）

1. **还原到旧转换的类型。** 若 D1 显示旧工程更接近 Keras，就用 D5 的对照表把新工程的类型配置改回旧值（`Precision`/`LayerName` 里显式指定），这是最稳的。
2. **舍入/饱和模式配置**（源码里是 `ConfigurableOptimizerPass`，默认不对任何层生效）：

```python
import hls4ml
opt = hls4ml.model.optimizer.get_optimizer('output_rounding_saturation_mode')
opt.configure(layers=['Activation', 'Conv2D', 'BatchNormalization'],   # 以你的层类名为准
              rounding_mode='AP_RND', saturation_mode='AP_SAT')
cfg['Flows'] = [...]   # 保持你现有的 flow，并确保该 pass 在其中
```

   在 bit_exact 流程里舍入只接受 `TRN`/`RND`，所以只能选 `AP_RND`（半入），不能选 `AP_RND_CONV`。
3. **BN 路径显式化**：给 BN 的 scale/bias/result 指定精度；比较「保留 BN 层」与「BN 折进卷积」两种做法，后者需要 §10 的重训练。
4. **并列项一致化**（见 §4.4），属于训练侧改动。

### 4.4 并列项（tie）问题

QKeras 的 `_round_through` 非随机分支是 `tf.round`，即**四舍六入五成双** [源码]；hls4ml bit_exact 流程里层级舍入只认 `TRN`/`RND`（`RND` 是半入）[源码]。当权重在 po2 网格、激活在 6 bit 网格时，预激活值落在很细的网格上，**恰好等于半个 LSB 的并列项并不罕见**，两种舍入在这些点上结果不同。单个并列项只差 1 LSB，但这是系统性的方向偏差，会逐层累积。这是 [推断]，是否是主因要由 §4.2 的判读表决定。

若确认是主因，两条路：
- (a) 训练侧换成半入舍入：写一个与硬件一致的自定义量化器（`floor(x+0.5)`），微调 10～20 个 epoch，使权重适应部署的舍入；
- (b) 在 hls4ml 侧找一个与五成双一致的配置（若 1.3.0 的 bit_exact 流不支持，就只能走 (a)）。

### 4.5 numpy 整数金模型（仲裁者）

按你们项目「Python 金模型先行」的约定，写一个与 h5 量化配置一致的 numpy 前向（逐层整数/定点运算，规则取自 QKeras 的量化器定义），在 256 张上做三方仲裁：

| numpy 金模型对 Keras | numpy 金模型对 csim | 结论 |
|---|---|---|
| 一致 | 不一致 | hls4ml 转换/配置有问题（按 §4.2 修） |
| 不一致 | 一致 | Keras 前向与你以为的硬件数学不一致（量化器用法、`alpha`、训练/推理模式） |
| 一致 | 一致 | 之前的差异来自评测路径，不是转换 |
| 都不一致 | — | 金模型自身有 bug，先修金模型 |

### 4.6 兜底：硬件感知微调

如果配置层面无法消除舍入差异，用 §4.5 的金模型规则做 QAT 微调：前向使用与硬件逐位一致的量化函数（`floor(x+0.5)`、饱和、同样的位宽与 BN 处理），反向用直通估计。10～20 个 epoch，验证集选点后在 1 万张上重测 csim。验收仍用 G1 的门。

**G1 全部通过前，不做实现、不上板、不替换 bit。**

---

## 5. G2：面积闭环

### 5.1 目标红线（沿用）

LUT<60 000（约 68%），DSP<500，BRAM_18K<160（约 62%），200 MHz 下 WNS≥0。用 `export_design -flow syn` 的结果核实，不以 csynth 估计为准（v3 §P3）。

### 5.2 方法

**步骤 1：逐实例归因表。** 在 D2 之后，你应该有两张表（基线 P4、A1'，同一转换）。把每个实例分成：卷积、BN、ReLU、池化、GAP、zeropad、FIFO、AXIS 适配。列出每类的 LUT/FF/DSP/BRAM，按「增量」排序。

**步骤 2：BN 流变窄（若 HA 成立）。** BN 后面紧跟 6 bit 的 relu 量化器，BN 的输出不需要 41 bit。用数据驱动的方法确定位宽：

1. 在 1 万张上用 trace 取每个 BN 输出的最大绝对值 `Mx` 与分布；
2. 整数位 `I = ceil(log2(Mx × 2)) + 1`（留 2× 余量）；
3. 小数位 `F = F_relu + g`，`F_relu` 是紧随其后的 relu 量化器的小数位，`g` 是保护位，依次试 `g = 2, 4, 6`；
4. 改类型后重跑 G1 的数值门：窄化版与宽版在 relu 之后必须**逐比特一致的比例 ≥99.99%**，且 csim 的 Top-1（1 万张）不降。不满足就加 `g`。

预期效果 [推断]：元素位宽 41/42 → 约 12～16 bit，每通道 BRAM18 从 3 个降到 1 个；BN 乘法器位宽同步缩小，DSP/LUT 下降。**这是否到达红线以实测为准。**

**步骤 3：强制浅 FIFO 不占 BRAM。** 这些 FIFO 深度只有 16/32，用 BRAM 是浪费。用 Vivado HLS 2020.1 支持的方式把它们绑定到 SRL 或 LUTRAM（`RESOURCE core=FIFO_SRL`/`FIFO_LUTRAM`，先在单层微基准上验证，确认指令名在 2020.1 里可用）。若 hls4ml 写出的 stream 指令里已有该选项就改源模板。

**步骤 4：FIFO 深度优化与 ReLU 合并**（v3 §P6）。在步骤 2 之后做，否则会按 41 bit 的位宽去优化。

**步骤 5：BN 折叠（可选，需重训练）。** 把 BN 折进卷积权重与偏置（QKeras 的 `QConv2DBatchnorm` 一类折叠层），硬件上只剩偏置加法与 po2 缩放。会改变训练图，因此放在 §10 的训练侧，只有步骤 2 达不到红线时才做。

### 5.3 面积门

| 项 | 门 |
|---|---|
| 步骤 2 后，基线 P4 的 BRAM_18K | ≤60 |
| 步骤 2 后，A1' 的 BRAM_18K | ≤160 |
| 步骤 2 后，A1' 的 LUT（综合后）| <60 000 |
| 数值 | 回到 G1 的门，不过就撤销该改动 |

---

## 6. G3：延迟闭环（全部 csynth 级别，可与 G1 并行）

### 6.1 conv1a 的 II=8

- 补丁：对 `kernel_data`（以及传给 dense 的 `data`）加 `#pragma HLS ARRAY_PARTITION variable=... complete`，补丁进入你们的 patch 列表并写根因注释。
- 验证：csynth 后 conv1a 的 `ReuseLoop` achieved II=1，该层周期从 263 568 降到约 `1156×(27+12)=45k`；输出逐比特与补丁前一致。
- 若补丁无效：把 D4 取到的完整消息贴给我，不要继续猜。

### 6.2 基线五层的慢（HL2）

v3 的 P5：给 `IndexLoop` 加 `PIPELINE II=1`，对基线 P4 配置重跑 csynth。判据与预测见 v3 §2 P5。在 D2 之后做，这样补丁前后对比的是同一个转换。

### 6.3 选点

G1/G2 过了之后，在 v3 §3 的前沿表上选点，但**用 D2/§5 的实测「每乘法器增量」替换理想周期模型**，并且重新核实：
- 每点都要重新跑 `rf_planner.py` 校验 RF 合法性；
- csynth 里同时读 II 与每层周期，确认没有第二个像 conv1a 那样的 II>1。

分级目标沿用 v3 §4（T1≤3.5 ms 且面积不高于基线；T2≤1.5 ms 且 LUT<60k、BRAM<70%）。

---

## 7. 综合与实现流程

1. **csynth**（每个候选，并行可做）：保存报告、日志、`parameters.h`、补丁清单、脚本 commit。
2. **`export_design -flow syn`**：得到真实 LUT/BRAM。通过面积门的才继续。
3. **完整实现**（新 bit，**不覆盖** `46987907…`）：沿用你们现有的 BD/Tcl，200 MHz，HP0 64-bit。输出 bit 与 hwh，命名带日期与变体名，记录 MD5。
4. **时序**：WNS≥0；不满足先查关键路径是否在 BN 乘法或宽 FIFO，再考虑降到 150 MHz 并按比例换算延迟。
5. **利用率**：写入 JSON，不覆盖旧报告。

只有 G1、G2 都通过的候选才允许进入 §8。

---

## 8. 端到端上板验证（E2E）

### 8.1 数据与协议

- **测试集**：固定顺序的 1 万张，保存成 `data/test10k_u8.npy` 与 `data/test10k_labels.npy`，所有环境（Keras、csim、板端、CPU 基线）用同一份。
- **输入打包**：直接复用已部署流程里的打包函数（6144 B 一帧），不要重写；板端读回 96 B（24 个 int32，scale 1024），PS 端除以 1024 后接 Dense。若是宽网（B2），按 §8.1 的规则改 `OUT_BYTES=OUT_DIM×4`。
- **0xAA 洞检查**：沿用你们现有做法，每帧检查输出区没有被覆写的残留。

### 8.2 板端流程

1. 按 `docs/porting_env_hardware_config.md` 的顺序：确认 `fpga0=operating` 之前不碰 `0x66C00000`、`0x80040000`；一次只开一个会话。
2. **已知好 bit 备份**：已部署 bit 与 hwh 改名为 `known_good_*`，MD5 记录在案。新 bit 用独立文件名，脚本里用参数 `BIT=...` 切换，不改默认值。
3. **烟雾测试**：先 8 张典型图 + 全黑 + 全白 + 棋盘 + 单通道饱和图，一共 12 张，对比**新设计的 csim**（不是旧 bit）：GAP 必须逐比特一致。极端输入专门用来测试饱和与回绕。
4. **精度运行**：1 万张全部过板，保存 `board_gap.npy`（N×24）、`board_pred.npy`、`lat_ms.npy`。每 1000 张打印一次进度与 0xAA 检查结果。
5. **复位策略**：`reset_each` 与 `no_reset` 各完整跑一遍（延迟分别报告；精度应一致）。
6. **重复性**：同一 bit 连续跑 3 次，第 2、3 次与第 1 次的 `board_gap` 逐比特一致；其中一次断电重启后再跑 100 张验证加载流程。

### 8.3 判定

用 `e2e_compare.py` 一次性给出结论：

```bash
python3 e2e_compare.py \
  --labels data/test10k_labels.npy --keras-pred results/keras_pred.npy \
  --board-pred results/board_pred.npy --board-gap results/board_gap.npy \
  --csim-gap results/csim_gap_first1000.npy --csim-pred results/csim_pred_first1000.npy \
  --lat-ms results/lat_ms.npy --out results/opt_v2/e2e_report.json
```

| 项 | 门 | 没过怎么办 |
|---|---|---|
| 板端 GAP 与 csim GAP | **前 1000 张逐比特一致**（硬性，脚本退出码 1） | 查数据路径、位宽/字节序、PS 缩放、DMA 时序；**不是**调 RF |
| 板端 Top-1 与 Keras Top-1 | 差 ≤0.5 点（1 万张） | 回到 G1 |
| 板端 vs csim 配对检验（前 1000 张）| p>0.05 且不一致对数=0 | 同上 |
| 延迟中位数 / p99 | 达到当前分级目标（T1/T2） | 回到 G3 |
| 0xAA 洞 | 全部为空 | 查缓冲与 DMA 长度 |
| 时序与利用率 | 见 §7 | 同 §7 |

### 8.4 CPU 对照（同一套 harness）

把 A53 上的 TFLite INT8（你们已有 12.23 ms、83%）在**同一份 1 万张**上重跑，输出同样格式的 JSON。最终对外只用一张表：

| 方案 | Top-1（1 万张）| 延迟中位数 / p99 | 功耗（若可测）| J/帧 |
|---|---|---|---|---|
| CPU TFLite INT8 | | | | |
| FPGA 已部署 bit（重测）| | | | |
| FPGA 新 bit | | | | |

注意：CPU 的 83% 是在哪个子集上量的要写清楚；若是 N=100，同样重测。

### 8.5 功耗（尽量做）

若板上有电流/电压监测（INA 之类或电源模块读数），空闲、CPU 基线运行、FPGA 运行三种状态各记录 60 秒平均，换算 J/帧。没有手段就明确写「未测」，不要估。

### 8.6 稳定性

- 1 万张全程无超时、无丢帧；
- 跑 30 分钟循环（可降到每 10 张取样比较）验证无漂移；
- 记录板温（若可读）与时钟（`pl0_ref`），防止结果受降频影响。

### 8.7 产物（沿用你们的交付惯例）

`results/opt_v2/e2e_report.json`、`docs/STATUS.md`（分层：已仿真 / 已上板 / 仅推断）、`docs/VERIFICATION_REPORT.md`（由回归脚本生成）、bit/hwh 与 MD5、补丁清单与根因注释、面试要点（诊断→定位→修复→上板验证，数字取自实测）。

---

## 9. 验收矩阵、停手与回退

| 阶段 | 通过条件 | 失败时 |
|---|---|---|
| D1–D6 | 六项结果齐全并写入 JSON | 缺哪项补哪项，不跳 |
| G1 | §4.1 的全部项 | 按 §4.2 判读表走；还不行就 §4.6；**全程不上板** |
| G2 | §5.3 | 回到 §5.2 下一步；步骤 5 才需要训练 |
| G3 | conv1a II=1；基线五层按 P5 结论处理；csynth 周期与模型一致 | 贴日志，不要猜 |
| 实现 | WNS≥0 且面积在红线内 | 降频/削面积，不超红线 |
| E2E | §8.3 的全部项 | 按表中「怎么办」处理 |

**停手条件**：任一步骤的改动让 G1 的数值门倒退，立即撤销该改动；一次只改一件事；每步先写预测值再运行。

**回退**：新 bit 与已部署 bit 并存，默认脚本指向 `known_good`；`known_good` 的 MD5（`46987907…` / `7576e1ed…`）每次会话开始先核对。

---

## 10. 之后的事（硬件稳定后）

1. **B1 的硬件域复测**：G1 闭合后，把 Q6 与 Q8 的 h5 各用同一固定流程转换，在 1 万张上各做一次 csim，配对检验。若 Q8−Q6 ≥1 点且 p<0.05，才重开 Q8；否则 B1 永久关闭。
2. **B0（固定架构的训练改进）**：先在同一固定 1 万张上重测 FP32 与 Q6（确认 Q6 不低于 FP32），再试更强的老师、KD 的 α/T 重扫、数据增强、更长的训练。判据：配对检验 p<0.05 且净增 ≥1 点（以 csim 为准，不以 Keras 为准）。
3. **B2（加宽）**：解除与 B1 的绑定。前置条件是 G2 完成并有「每乘法器面积」的实测数。先做中间档 24/28/32（MAC 约 10.43 M，约 2.06×），再看 32/40/48；每个候选先用 `rf_planner.py --widen` 校验 RF，再按实测面积判断。
4. **BN 折叠 + 硬件感知 QAT**：若 §5.2 步骤 2 达不到红线，或 §4.4 需要换舍入，就把训练图改成 `QConv2DBatchnorm` 一类的折叠形式并用与硬件一致的量化函数训练。

### 会话切分建议（每个会话的出口都是一个 JSON）

| 会话 | 内容 | 出口 |
|---|---|---|
| S1 | D1–D6 | 三方数值表、基线 csynth、类型对照表、1 万张 csim |
| S2 | G1（逐层二分 → 修法 → 复测）| `g1_report.json`，数值门通过或明确的根因 |
| S3 | G2 + G3 的 csynth/syn（面积与 II）| 面积门与 II 结论 |
| S4 | 完整实现，选定候选 | 新 bit/hwh + MD5 + 时序/利用率 |
| S5 | E2E 上板与 CPU 对照 | `e2e_report.json` 与对照表 |
| S6 | 文档与作品集产物 | STATUS/VERIFICATION/面试要点 |

---

## 附录 A：本轮核对过的源码事实

| 事实 | 位置 |
|---|---|
| QKeras 非随机舍入是 `tf.round`（四舍六入五成双）| QKeras 0.9.0 `quantizers.py::_round_through` |
| hls4ml 的 `output_rounding_saturation_mode` 默认对任何层都不生效，模式默认 None（用编译器默认）| `model/optimizer/passes/qkeras.py` |
| bit_exact 流程对输入量化器的舍入只接受 `TRN`/`RND`，饱和模式不一致会警告「可能破坏逐位精确」| `model/optimizer/passes/bit_exact.py`（约 970–993 行） |
| hls4ml 的 QKeras 量化器解析里 `RND_CONV`→`np.round`，`TRN`→`np.floor`，其他会报错 | `model/quantizers.py::_resolve_rounding_mode` |
| `bit_exact` 作为转换参数写入 `HLSConfig['Model']['BitExact']` | `converters/__init__.py` |
| `RF≤n_in` 的 dense 分支里所有并行通道读同一个下标 `in_index=ir`；若 `data` 没有被完全分块，16 个通道对 2 端口存储 → II=8 | `nnet_dense_resource.h::dense_resource_rf_leq_nin` + 你的 csynth 消息（后者是 [推断] 的依据）|

## 附录 B：D1–D6 的记录字段（每个一个 JSON）

```
{ "id": "D1", "date": "...", "env": {"hls4ml": "...", "qkeras": "...", "tf": "...", "vivado_hls": "..."},
  "inputs": {"h5": "...", "h5_md5": "...", "n_images": 1000, "order": "fixed test order"},
  "results": {...}, "decision": "...", "next": "..." }
```

## 附录 C：我不能判断的几点

1. 旧工程是否还能编译、csim 是否能在同一批 1000 张上运行，取决于你的目录；若不能，D1 退化为「新 csim vs Keras vs numpy 金模型」。
2. conv1b…conv3b 为何没有 conv1a 那样的 II=8，我没有数据；D4 的目的就是要回答这个问题。
3. Vivado HLS 2020.1 里 FIFO 的 `RESOURCE core=FIFO_SRL` 等指令名与行为，请以 UG902 为准，并先在单层微基准上验证。
