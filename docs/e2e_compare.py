#!/usr/bin/env python3
"""
e2e_compare.py -- 端到端比对：Keras / csim / 板端 三方的 GAP 与 Top-1，加延迟统计。
输入均为 .npy，顺序必须是同一份固定顺序测试集：
  --labels      labels.npy            (N,)  int
  --keras-pred  keras_pred.npy        (N,)  int   Keras 全模型 Top-1 预测
  --csim-gap    csim_gap.npy          (M,24) 浮点或 int(已除以 scale)  M<=N，前 M 张
  --board-gap   board_gap.npy         (N,24) 同上单位
  --board-pred  board_pred.npy        (N,)  int   板端 GAP + PS Dense 的预测
  --lat-ms      lat_ms.npy            (N,)  每帧板端延迟(ms)，可选
输出 JSON 到 --out；任一硬性门不过则退出码 1。
硬性门：board_gap 与 csim_gap 在前 M 张上必须逐比特一致(max|Δ|==0)。
"""
import argparse, json, sys
import numpy as np
from scipy.stats import binomtest

def mcnemar(a_ok, b_ok):
    b = int(((a_ok == 1) & (b_ok == 0)).sum()); c = int(((a_ok == 0) & (b_ok == 1)).sum())
    p = 1.0 if b + c == 0 else binomtest(min(b, c), b + c, 0.5).pvalue
    return dict(a_only=b, b_only=c, p=float(p))

def main():
    ap = argparse.ArgumentParser()
    for k in ("labels", "keras-pred", "board-pred", "board-gap"): ap.add_argument(f"--{k}", required=True)
    ap.add_argument("--csim-gap"); ap.add_argument("--csim-pred"); ap.add_argument("--lat-ms")
    ap.add_argument("--out", default="e2e_report.json")
    a = ap.parse_args()
    y = np.load(a.labels); kp = np.load(a.keras_pred); bp = np.load(a.board_pred); bg = np.load(a.board_gap)
    N = len(y); rep = dict(N=N, pass_hard_gate=True)
    rep["top1"] = dict(keras=float((kp == y).mean()), board=float((bp == y).mean()))
    rep["mcnemar_board_vs_keras"] = mcnemar((bp == y).astype(int), (kp == y).astype(int))
    rep["board_vs_keras_top1_gap_pt"] = 100 * (rep["top1"]["keras"] - rep["top1"]["board"])
    if a.csim_gap:
        cg = np.load(a.csim_gap); M = len(cg)
        d = np.abs(bg[:M].astype(np.float64) - cg.astype(np.float64))
        rep["gap_board_vs_csim"] = dict(M=M, max_abs=float(d.max()), mean_abs=float(d.mean()),
                                        n_images_with_any_diff=int((d.max(axis=1) > 0).sum()))
        if d.max() != 0: rep["pass_hard_gate"] = False
    if a.csim_pred:
        cp = np.load(a.csim_pred); M = len(cp)
        rep["top1"]["csim_first_M"] = float((cp == y[:M]).mean())
        rep["top1"]["board_first_M"] = float((bp[:M] == y[:M]).mean())
        rep["mcnemar_board_vs_csim_firstM"] = mcnemar((bp[:M] == y[:M]).astype(int), (cp == y[:M]).astype(int))
    if a.lat_ms:
        t = np.load(a.lat_ms)
        rep["latency_ms"] = dict(median=float(np.median(t)), p99=float(np.percentile(t, 99)),
                                 mean=float(t.mean()), std=float(t.std()), n=int(len(t)))
    json.dump(rep, open(a.out, "w"), indent=2, ensure_ascii=False)
    print(json.dumps(rep, indent=2, ensure_ascii=False))
    sys.exit(0 if rep["pass_hard_gate"] else 1)

if __name__ == "__main__":
    main()
