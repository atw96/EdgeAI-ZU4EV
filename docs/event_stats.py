#!/usr/bin/env python3
"""
event_stats.py -- 稀有事件(如 0xAA 空洞)的发生率、95% 区间与配置间比较。
用法:  python3 event_stats.py base:0:623787 fast_div8:1:135660 fast_div10:1:959610
       每项 名称:事件数:帧数 ; 第一项作为基线。
输出: 每百万帧发生率 + 精确泊松(Garwood)95% 区间；0 事件时给出 95% 上界(约 3/N)；
      每个配置相对基线的条件二项检验(H0: 发生率相同)；以及「合并」后的整体发生率。
也可 --need-frames RATE_PER_M 计算观察到至少 K 个事件所需帧数的粗估(用于设计过夜 soak)。
"""
import argparse, sys, math

# 纯 Python 实现（不依赖 scipy / 新版 numpy，可在旧环境直接运行）
def _pois_cdf(k, mu):
    return sum(math.exp(-mu + i * math.log(mu) - math.lgamma(i + 1)) for i in range(k + 1)) if mu > 0 else 1.0

def _bisect(f, lo, hi, it=200):
    for _ in range(it):
        mid = (lo + hi) / 2
        if f(mid) > 0: hi = mid
        else: lo = mid
    return (lo + hi) / 2

def binomtest_p(k, n, p0):
    """精确双侧二项检验：概率不大于观测概率的所有结果之和。"""
    pm = [math.exp(math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1)
                   + (i * math.log(p0) if i else 0) + ((n - i) * math.log(1 - p0) if n - i else 0)) for i in range(n + 1)]
    return min(1.0, sum(x for x in pm if x <= pm[k] * (1 + 1e-9)))

def ci(k, n):
    """精确泊松(Garwood) 95% 区间，返回每百万帧。"""
    lo = 0.0 if k == 0 else _bisect(lambda mu: (1 - _pois_cdf(k - 1, mu)) - 0.025, 1e-12, 1e4)   # P(X>=k|mu)=0.025
    hi = _bisect(lambda mu: 0.025 - _pois_cdf(k, mu), 1e-12, 1e4)                                   # P(X<=k|mu)=0.025
    return lo / n * 1e6, hi / n * 1e6

ap = argparse.ArgumentParser(); ap.add_argument("items", nargs="*")
ap.add_argument("--need-frames", type=float, help="假设发生率(每百万帧)，估计观察到 --events 个事件所需帧数")
ap.add_argument("--events", type=int, default=10)
a = ap.parse_args()
if a.need_frames:
    print(f"发生率 {a.need_frames}/M 帧：期望观察到 {a.events} 个事件约需 {a.events / a.need_frames * 1e6:,.0f} 帧"); sys.exit()
rows = []
for it in a.items:
    n, k, f = it.split(":"); rows.append((n, int(k), int(f)))
if not rows: sys.exit(__doc__)
tk = sum(r[1] for r in rows); tf = sum(r[2] for r in rows)
print(f"{'配置':14s}{'事件':>6s}{'帧数':>12s}{'每百万帧':>10s}{'95%区间':>20s}")
for n, k, f in rows:
    lo, hi = ci(k, f); print(f"{n:14s}{k:6d}{f:12,d}{k/f*1e6:10.2f}   [{lo:6.2f}, {hi:7.2f}]")
print(f"{'合并':14s}{tk:6d}{tf:12,d}{tk/tf*1e6:10.2f}   [{ci(tk, tf)[0]:6.2f}, {ci(tk, tf)[1]:7.2f}]")
if len(rows) > 1:
    b = rows[0]
    for n, k, f in rows[1:]:
        tot = b[1] + k
        if tot == 0: print(f"{n} vs {b[0]}: 两者都无事件，无法比较"); continue
        p = binomtest_p(k, tot, f / (f + b[2]))
        print(f"{n} vs {b[0]}: 条件二项检验 p = {p:.3f}")
    if len(rows) > 2:
        k_base = b[1]; f_base = b[2]; k_rest = tk - k_base; f_rest = tf - f_base
        p = binomtest_p(k_base, tk, f_base / tf) if tk else 1.0
        print(f"基线 vs 其余合并(H0 同率): 基线 {k_base} 次/{f_base:,} 帧，其余 {k_rest} 次/{f_rest:,} 帧，p = {p:.3f}")
