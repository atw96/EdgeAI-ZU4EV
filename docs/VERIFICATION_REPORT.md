# 验证记录（2026-10-18）

候选：窄精度（`BIT_EXACT=0`）A1'，`kernel_data` 为 hls4ml 生成的 complete 分块，FIFO 深度用 aggressive 档。Bitstream `deploy/opt_v2/A1shallow/cifar10_accel.bit`，MD5 `334e27454dcb05d179d6d188b7d404c3`。已部署 bit `46987907f8177883048b705fdf68c370` 与 hwh `7576e1edbc8708cdaad98bbaa1f50baa` 未改。Q6 h5 大小仍是 153920 字节，MD5 `ee06a3ada0cae8575eeb1e39ffa3932b`。

## 诊断

D1。3.3 个点（Top-1 78.5%，MAE 0.087）只属于 `BIT_EXACT=1` 的 41 位 BN 路径。当前窄精度在 1000 张上 MAE 0.026、Top-1 81.6%，Keras 是 81.8%。已部署导出工程的 `defines.h` 与当前工程逐字节相同。

D2。深 FIFO 的 P4 是 675391 拍、BRAM_18K 568；A1' 浅 FIFO 后仍是 175350 拍，BRAM_18K 22。`r=17` 只配对旧板端 57.43 ms。

D3。1 万张 csim Top-1 81.78%，Keras 81.90%，差 0.12 点，MAE 0.0260。`csim.exe` 曾停在 9538 行，余下 462 张补跑后拼接。记录在 `results/opt_v2/v4_d3.json`。

D4。conv1a 的 9.5 倍来自把 `kernel_data` 改成 cyclic factor 4（36997 拍对 263573 拍）。该替换已从默认补丁删除。IndexLoop 没有改变 P4 顶层周期。

D5。窄精度卷积/BN 为 `ap_fixed<16,8,AP_RND_CONV,AP_SAT,0>`。`BIT_EXACT=1` 的 `bn_conv1a` 结果是 `ap_fixed<41,8>`。

D6。同一 1000 张上 Keras 全模型 Top-1 复现为 81.8%。`input_qact` 落在 1/64 网格。`dense_head.npz` 与 Keras `predictions` 层的预测逐样本一致。

## 上板

板子地址用环境变量 `BOARD_IP`。加载前若状态不是 `operating`，先 `FORCE_PL_RELOAD`，再把 HP0 织物宽度设为 64 位，然后才访问 DMA。漏掉 HP0 修正时，四张极端图全部出现 0xAA 空洞。

1 万张：板端 81.78%，Keras 81.90%，McNemar p=0.46。板端与 csim 的 GAP 最大差为 0。`reset_each` 与 `no_reset` 逐 LSB 一致。三次重复的前 200 张逐 LSB 一致。延迟中位数 2.099 ms，p99 2.143 ms。

今早重新加载后，前 200 张与 csim 的最大 LSB 差仍是 0。

`docs/e2e_compare.py` 在 `edgeai_39` 里无法 import `scipy.stats`（NumPy 1.19 与当前 SciPy 不匹配）。同一套门由 `scripts/opt_v2/v4_e2e_fallback.py` 计算，1 万张硬性门通过。结果在 `results/opt_v2/e2e_report.json`。

## 面积与时序

布线 WNS +0.090 ns，WHS +0.010 ns，TNS 0。LUT as Logic 33459，DSP 207，BRAM tile 20。红线内。

## 合成输入（v5）

729 张（种子 20261018）。第一次用空洞检测解码时，灰度 0–51 等 83 张和 csim 不一致；噪声和局部方块是 0 张失败。回读的 S2MM 原始 96 字节与 csim 逐比特一致，四种前序条件下全黑原始输出相同。原因是 `dram_has_hole_pair_layout` 把真实的 0 通道当成 32 位 HP 空洞。串行解码重跑后 729 张最大差 0 LSB。csim 对 Keras 仍有 44 张超过 400 LSB，最大 913，在常数低灰度上，按软门记录，不改类型。

先前四张极端图里全黑的 870 LSB 是同一次误解码。全白、棋盘、单通道饱和本来就与 csim 一致。

功耗和板上 TFLite 的 1 万张重测没有做。运行时钟 `pl0_ref` 为 99942389 Hz，HWH 的 PL0 目标是 199.998 MHz。
