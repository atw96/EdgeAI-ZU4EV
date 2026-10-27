#!/usr/bin/env python3
"""
make_synth_suite.py -- 生成端到端「输入域覆盖」合成图像集 (uint8, NHWC, 32x32x3)，固定种子，可复现。
输出 synth_suite.npz: images(N,32,32,3 uint8), names(N,), cats(N,)   以及 synth_suite.json(类别->下标范围)
类别:
  const_gray   : 256 张常数灰度 0..255 (三通道同值)            -> 找「全黑」问题的触发边界
  const_chan   : 3x(0,1,2,4,8,16,32,64,128,192,254,255)        -> 单通道常数，其他通道为 0
  extreme_mix  : 全黑/全白/各通道 0|255 的 8 种组合
  checker      : 周期 1,2,4,8 的黑白棋盘 + 反相
  gradient     : 水平/垂直/对角渐变，各通道独立方向
  noise_uniform: 200 张均匀噪声
  patch_mix    : 200 张自然式随机底色 + 随机 0/255 方块 (检验局部极值是否触发)
  near_black   : 全黑上随机 k 个像素置 v (k=1,4,16,64; v=1,8,64,255)
"""
import json, numpy as np
rng = np.random.default_rng(20261018)
imgs, names, cats = [], [], []
def add(a, n, c): imgs.append(a.astype(np.uint8)); names.append(n); cats.append(c)
Z = np.zeros((32, 32, 3), np.uint8)
for g in range(256): add(Z + g, f"gray_{g}", "const_gray")
for ch in range(3):
    for v in (0, 1, 2, 4, 8, 16, 32, 64, 128, 192, 254, 255):
        a = Z.copy(); a[..., ch] = v; add(a, f"chan{ch}_{v}", "const_chan")
for m in range(8):
    a = Z.copy()
    for ch in range(3):
        a[..., ch] = 255 if (m >> ch) & 1 else 0
    add(a, f"extreme_{m:03b}", "extreme_mix")
yy, xx = np.mgrid[0:32, 0:32]
for p in (1, 2, 4, 8):
    cb = (((yy // p) + (xx // p)) % 2 * 255).astype(np.uint8)
    add(np.stack([cb] * 3, -1), f"checker_p{p}", "checker"); add(255 - np.stack([cb] * 3, -1), f"checker_inv_p{p}", "checker")
ramp = (np.arange(32) * 255 // 31).astype(np.uint8)
for i, (fx, fy) in enumerate([(1, 0), (0, 1), (1, 1), (-1, 0), (0, -1)]):
    a = np.zeros((32, 32, 3), np.uint8)
    for ch in range(3):
        s = [1, -1, 1][ch] if i >= 2 else 1
        r = (fx * xx + fy * yy) % 32
        a[..., ch] = ramp[r] if s > 0 else 255 - ramp[r]
    add(a, f"gradient_{i}", "gradient")
for i in range(200): add(rng.integers(0, 256, (32, 32, 3)), f"noise_{i}", "noise_uniform")
for i in range(200):
    a = np.clip(rng.normal(rng.integers(40, 200), 25, (32, 32, 3)), 0, 255)
    for _ in range(rng.integers(1, 5)):
        y0, x0, s = rng.integers(0, 28), rng.integers(0, 28), rng.integers(2, 9)
        a[y0:y0 + s, x0:x0 + s, :] = rng.choice([0, 255])
    add(a, f"patch_{i}", "patch_mix")
for k in (1, 4, 16, 64):
    for v in (1, 8, 64, 255):
        a = Z.copy().reshape(-1, 3)
        idx = rng.choice(1024, k, replace=False); a[idx] = v
        add(a.reshape(32, 32, 3), f"nearblack_k{k}_v{v}", "near_black")
X = np.stack(imgs); cats_a = np.array(cats)
np.savez("synth_suite.npz", images=X, names=np.array(names), cats=cats_a)
rngs = {c: [int(np.where(cats_a == c)[0][0]), int(np.where(cats_a == c)[0][-1]) + 1] for c in dict.fromkeys(cats)}
json.dump(dict(N=int(len(X)), ranges=rngs), open("synth_suite.json", "w"), indent=1)
print(len(X), rngs)
