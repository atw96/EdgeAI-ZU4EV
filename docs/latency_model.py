#!/usr/bin/env python3
"""
latency_model.py -- 传输窗口模型  window_ms = a_ms + cycles / (f_MHz * 1e3)

子命令
  fit      用时钟梯度实测 (f_MHz, window_ms) 拟合 a(与时钟无关的固定部分) 与 cycles(随时钟缩放的 PL 周期)
           python3 latency_model.py fit --csv ladder.csv          # 列: f_mhz,window_ms
  ladder   按「忙等」基准预测各分频档的等待时间，并模拟 q 毫秒步长轮询造成的量化（解释窗口平台），同时标注 MMCM 规格与签核频率
           python3 latency_model.py ladder --wait0 1.719 --f0 99.942 --q 0.62
  project  按已校准的 a / PS 部分，对候选设计和时钟做预测（模型预测，不是实测）
           python3 latency_model.py project --a-ms 0.276 --ps-ms 0.277

约定
  RC1 已知: csynth 顶层 175350 拍 = 最大层 147456 + 尾部 27894；实测窗口 2.030 ms @99.942 MHz
  候选的 csynth 顶层周期 ≈ 最大层周期 + 尾部（尾部先按 RC1 的 27894 作上界，csynth 出来后替换）
"""
import argparse, csv, sys
import numpy as np

def fit(path):
    rows = [(float(r["f_mhz"]), float(r["window_ms"])) for r in csv.DictReader(open(path))]
    if len(rows) < 3: sys.exit("至少需要 3 个时钟点")
    f = np.array([r[0] for r in rows]); w = np.array([r[1] for r in rows])
    x = 1.0 / (f * 1e3)                       # ms per cycle
    A = np.vstack([np.ones_like(x), x]).T
    (a, cyc), *_ = np.linalg.lstsq(A, w, rcond=None)
    pred = A @ np.array([a, cyc]); ss = ((w - w.mean()) ** 2).sum()
    r2 = 1 - ((w - pred) ** 2).sum() / ss if ss > 0 else 1.0
    print(f"a(固定部分) = {a:.4f} ms    cycles(随时钟缩放) = {cyc:,.0f}    R^2 = {r2:.5f}")
    for fi, wi, pi in zip(f, w, pred): print(f"  f={fi:8.2f} MHz  实测 {wi:.4f} ms  拟合 {pi:.4f} ms  残差 {wi-pi:+.4f}")
    print("判读: cycles 应接近 csynth 顶层周期(RC1=175350)；a 为 DMA/驱动等固定开销。残差有系统性趋势说明模型不成立(例如存在随时钟变化的第三项)。")

def project(a_ms, ps_ms, tail, freqs):
    designs = [("RC1 (A1')", 147456), ("A2-L", 36864), ("A2-M", 18432), ("A2-H", 12288)]
    print(f"a={a_ms} ms  ps={ps_ms} ms  tail={tail} cyc  (均为模型输入)")
    print(f"{'设计':10s}{'f(MHz)':>9s}{'csynth周期':>12s}{'窗口ms':>9s}{'端到端ms':>10s}{'PL间隔ms':>10s}{'PL-only FPS':>12s}")
    for name, mx in designs:
        for f in freqs:
            top = mx + tail; win = a_ms + top / (f * 1e3); e2e = win + ps_ms; itv = mx / (f * 1e3)
            print(f"{name:10s}{f:9.1f}{top:12,d}{win:9.3f}{e2e:10.3f}{itv:10.3f}{1e3/itv:12.0f}")

def ladder(wait0, f0, rpll, divs, q, start, extra, vco_mult, vco_lo, vco_hi, f_sign):
    """按 wait(f)=wait0*f0/f 预测忙等下的等待时间，并给出 q(ms) 步长轮询量化后的「看到的窗口」与 MMCM 规格判定。"""
    import math
    print(f"忙等基准 wait0={wait0} ms @ {f0} MHz；轮询步长 q={q} ms；start={start} ms；其余={extra} ms；RPLL={rpll} MHz")
    print(f"{'DIV0':>5s}{'f(MHz)':>9s}{'VCO(MHz)':>10s}{'MMCM规格':>9s}{'<=签核':>7s}{'忙等wait':>10s}{'忙等窗口':>10s}{'轮询看到的窗口':>16s}")
    for d in divs:
        f = rpll / d; vco = vco_mult * f; w = wait0 * f0 / f
        ok = "合规" if vco_lo <= vco <= vco_hi else "规格外"
        sg = "是" if f <= f_sign else "否"
        seen = start + math.ceil(w / q) * q + extra
        print(f"{d:5d}{f:9.2f}{vco:10.1f}{ok:>9s}{sg:>7s}{w:10.3f}{start + w:10.3f}{seen:16.3f}")

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest="cmd", required=True)
    p3 = sp.add_parser("ladder")
    p3.add_argument("--wait0", type=float, default=1.719); p3.add_argument("--f0", type=float, default=99.942)
    p3.add_argument("--rpll", type=float, default=1499.136); p3.add_argument("--divs", default="15,14,13,12,11,10,9,8,7")
    p3.add_argument("--q", type=float, default=0.62); p3.add_argument("--start", type=float, default=0.149); p3.add_argument("--extra", type=float, default=0.017)
    p3.add_argument("--vco-mult", type=float, default=6.0); p3.add_argument("--vco-lo", type=float, default=800.0); p3.add_argument("--vco-hi", type=float, default=1600.0)
    p3.add_argument("--f-signoff", type=float, default=200.0)
    p1 = sp.add_parser("fit"); p1.add_argument("--csv", required=True)
    p2 = sp.add_parser("project"); p2.add_argument("--a-ms", type=float, default=0.276); p2.add_argument("--ps-ms", type=float, default=0.277)
    p2.add_argument("--tail-cycles", type=int, default=27894); p2.add_argument("--freqs", default="99.94,150,171.3,199.9")
    a = ap.parse_args()
    if a.cmd == "ladder": ladder(a.wait0, a.f0, a.rpll, [int(x) for x in a.divs.split(",")], a.q, a.start, a.extra, a.vco_mult, a.vco_lo, a.vco_hi, a.f_signoff)
    elif a.cmd == "fit": fit(a.csv)
    else: project(a.a_ms, a.ps_ms, a.tail_cycles, [float(x) for x in a.freqs.split(",")])
