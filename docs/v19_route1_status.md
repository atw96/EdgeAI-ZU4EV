# v19 Route 1 调试状态（2026-06-20）

## 目标

- 平台：ZU4EV，CIFAR-10，GAP-only PL + PS Dense head
- 配置：`OUT_DIM=24 OUT_BYTES=92 OUT_LAYOUT=gap_ps OUT_FIXED_SCALE=256`
- 门禁：**csim + PS Dense Top-1 ≥ 75%**（主）；MAE 辅助

## 已采纳路线：Route 1（bit_exact）

1. QAT 图内嵌 `input_qact`（`QActivation` + `quantized_bits(6,0,alpha='auto_po2')`）
2. hls4ml 1.3 `BackendConfig.bit_exact=True`，**不手调 PREC**
3. Plan B（profiling / v17 / conv1ab 手调位宽）已废弃并自仓库移除

## 当前精度（40 epoch input_qact fine-tune 后）

| 路径 | Top-1 | 备注 |
|------|-------|------|
| Keras 全模型 / bench | ~80–81% | `verify_q6_bench_accuracy.py` |
| csim GAP + PS Dense | **12%** | 主门禁 **未通过** |
| csim vs Keras GAP MAE | ~0.44 | 辅助 WARN |
| 板端 benchmark | ~10% | 与 csim 量级一致，非 DMA 独有问题 |

**结论**：Keras 量化模型正常；HLS csim 与 Keras 仍严重偏离。更长 fine-tune 仅将 csim Top-1 从 7% 提到 12%，根因仍在 HLS 数值链 / 输入量化对齐，而非 Plan B 手调位宽。

## 推荐主流程

```bash
# WSL，conda edgeai_39 + edgeai_hls4ml13
cd /path/to/EdgeAI-ZU4EV_Claude
FT_EPOCHS=40 CSIM_TOP1_MIN=75 bash scripts/run_v19_qat_resume.sh
tail -f results/v19_qat_pipeline.log
cat results/v19_route1_gates.json
```

环境修复：`scripts/ensure_edgeai39_protobuf.sh`（TF 2.6 需 protobuf 3.20.x）

## 下一步诊断（未阻塞提交）

- `bash scripts/run_v19_csim_keras_layer_align.sh` — 逐层 MAE，定位首错层
- `bash scripts/run_v19_p0_layer_trace.sh` — hls4ml trace 对比

## 已清理内容

运行 `bash scripts/cleanup_repo_for_git.sh` 可删除：

- Plan B / v8–v18 实验脚本
- `notebooks/hls4ml_prj.bak*`、运行 log、大型中间 JSON
