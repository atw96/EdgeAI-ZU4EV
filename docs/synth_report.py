#!/usr/bin/env python3
"""
synth_report.py -- 合成输入集上 板端/csim/Keras 的 GAP 对比，按类别汇总，并定位 const_gray 的触发边界。
  --suite synth_suite.npz  --board board_gap.npy  --csim csim_gap.npy  [--keras keras_gap.npy]
  --scale 1024            (GAP 的 LSB = 1/scale；若输入文件已是浮点则 --scale 1 并用 --lsb 指定 LSB)
  --nat-max-lsb 266       自然图像 1 万张里 csim 对 Keras 的 GAP 最大差(以 LSB 计)，用于标定门
硬门: 板端 == csim (逐比特)。软门: csim 对 Keras <= 1.5 * nat-max-lsb。
"""
import argparse, json, sys
import numpy as np
ap = argparse.ArgumentParser()
ap.add_argument("--suite", required=True); ap.add_argument("--board", required=True); ap.add_argument("--csim", required=True)
ap.add_argument("--keras"); ap.add_argument("--lsb", type=float, default=None)
ap.add_argument("--scale", type=float, default=None)
ap.add_argument("--nat-max-lsb", type=float, default=266)
ap.add_argument("--out", default="synth_report.json")
a = ap.parse_args()
if a.scale is not None:
    a.lsb = 1.0 / a.scale
elif a.lsb is None:
    a.lsb = 1.0 / 1024.0
S = np.load(a.suite, allow_pickle=True); names, cats = S["names"], S["cats"]
B, C = np.load(a.board).astype(np.float64), np.load(a.csim).astype(np.float64)
K = np.load(a.keras).astype(np.float64) if a.keras else None
lsb = lambda d: np.abs(d).max(axis=1) / a.lsb
bc = lsb(B - C); ck = lsb(C - K) if K is not None else None
rep = dict(n=int(len(names)), hard_fail=[], soft_fail=[], by_cat={})
for c in dict.fromkeys(cats.tolist()):
    m = cats == c
    d = dict(n=int(m.sum()), board_vs_csim_fail=int((bc[m] > 0).sum()), board_vs_csim_max_lsb=float(bc[m].max()))
    if ck is not None:
        d["csim_vs_keras_max_lsb"] = float(ck[m].max()); d["csim_vs_keras_over_gate"] = int((ck[m] > 1.5 * a.nat_max_lsb).sum())
    rep["by_cat"][c] = d
for i in np.where(bc > 0)[0]: rep["hard_fail"].append(dict(name=str(names[i]), board_vs_csim_lsb=float(bc[i])))
if ck is not None:
    for i in np.where(ck > 1.5 * a.nat_max_lsb)[0]: rep["soft_fail"].append(dict(name=str(names[i]), csim_vs_keras_lsb=float(ck[i])))
g = [(int(str(n).split("_")[1]), bc[i]) for i, n in enumerate(names) if str(n).startswith("gray_")]
if g:
    bad = [v for v, d in g if d > 0]
    rep["const_gray_bad_levels"] = bad if len(bad) <= 40 else f"{len(bad)} levels, min={min(bad)}, max={max(bad)}"
json.dump(rep, open(a.out, "w"), indent=1, ensure_ascii=False)
print(json.dumps(rep["by_cat"], indent=1, ensure_ascii=False)); print("hard_fail:", len(rep["hard_fail"]), "soft_fail:", len(rep["soft_fail"]))
print("const_gray_bad_levels:", rep.get("const_gray_bad_levels"))
sys.exit(1 if rep["hard_fail"] else 0)
