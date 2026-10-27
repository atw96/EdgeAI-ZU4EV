#!/usr/bin/env python3
"""
rf_planner.py -- 为 hls4ml io_stream + Strategy=Resource 的卷积网络枚举【合法】ReuseFactor，
并在乘法器预算下做 MAC 比例均衡分配。

合法性规则逐字对应 hls4ml 1.3.0 backends/fpga/fpga_backend.py::_validate_reuse_factor:
    multfactor = min(n_in, rf); mult_limit = ceil(n_in*n_out/multfactor)
    ok = (mult_limit % n_out == 0 or rf >= n_in) and (rf % n_in == 0 or rf < n_in) and (n_in*n_out) % rf == 0
Conv2D: n_in = Cin*kh*kw, n_out = Cout。 P(并行乘法器) = n_in*n_out/RF。
周期模型(理想, 无 II 额外开销): layer_cycles = out_pixels * RF。

用法:  python3 rf_planner.py                # 打印当前网络的合法 RF 表与方案
       python3 rf_planner.py --widen 32,32,40,40,48,48
可在 edgeai_hls4ml13 环境里用 hls4ml 自带函数交叉校验:  --crosscheck
"""
import argparse, math, itertools, json

def valid_rf(n_in, n_out, rf):
    mult = min(n_in, rf)
    lim = math.ceil(n_in * n_out / mult)
    ok = (lim % n_out == 0 or rf >= n_in)
    ok = ok and (rf % n_in == 0 or rf < n_in)
    ok = ok and ((n_in * n_out) % rf == 0)
    return ok

def valid_rfs(n_in, n_out):
    return [rf for rf in range(1, n_in * n_out + 1) if valid_rf(n_in, n_out, rf)]

def dense_variant(n_in, rf):
    # 与 nnet_dense_resource.h::dense_resource 的分支一致
    if rf <= n_in: return "rf_leq_nin"          # 无 IndexLoop
    if rf % n_in == 0: return "rf_gt_nin_rem0"  # 含 IndexLoop(RF 次迭代, 内含 %)
    return "rf_gt_nin"

def layers(ch=(16, 16, 20, 20, 24, 24), hw=(32, 32, 16, 16, 8, 8), cin0=3):
    names = ["conv1a", "conv1b", "conv2a", "conv2b", "conv3a", "conv3b"]
    out, cin = [], cin0
    for n, c, s in zip(names, ch, hw):
        out.append(dict(name=n, n_in=cin * 9, n_out=c, px=s * s, macs=s * s * cin * 9 * c))
        cin = c
    return out

def table(L):
    for l in L:
        l["valid"] = valid_rfs(l["n_in"], l["n_out"])
    return L

def plan_balanced(L, p_budget, leq_only=True):
    """在 sum(P)<=p_budget 下最小化 max_i(px_i*RF_i)。对每个候选瓶颈 T 贪心取满足 px*RF<=T 的最大 RF(最小 P)。
    leq_only=True: 只用 RF<=n_in (rf_leq_nin 分支, 无 IndexLoop 风险)。"""
    cands = sorted({l["px"] * rf for l in L for rf in l["valid"]})
    best = None
    for T in cands:
        sel, ptot, ok = [], 0, True
        for l in L:
            rfs = [rf for rf in l["valid"] if l["px"] * rf <= T and (not leq_only or rf <= l["n_in"])]
            if not rfs: ok = False; break
            rf = max(rfs); p = l["n_in"] * l["n_out"] // rf
            sel.append((l["name"], rf, p)); ptot += p
        if ok and ptot <= p_budget:
            best = (T, sel, ptot); break
    return best

def report(L, label, rfs):
    tot_p = tot_c = 0; mx = 0; rows = []
    for l, rf in zip(L, rfs):
        assert valid_rf(l["n_in"], l["n_out"], rf), f"{l['name']} RF={rf} 非法"
        p = l["n_in"] * l["n_out"] // rf; c = l["px"] * rf
        rows.append((l["name"], rf, p, c, dense_variant(l["n_in"], rf)))
        tot_p += p; tot_c += c; mx = max(mx, c)
    print(f"\n== {label}  ΣP={tot_p}  max_stage={mx} cyc ({mx*5e-6:.3f} ms@200MHz)  Σstages={tot_c} cyc ({tot_c*5e-6:.3f} ms)")
    for r in rows: print(f"   {r[0]:7s} RF={r[1]:5d}  P={r[2]:4d}  stage={r[3]:7d} cyc  [{r[4]}]")
    return dict(label=label, rf=rfs, sumP=tot_p, max_stage=mx, sum_stage=tot_c)

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--widen", default=None, help="6 个通道数, 如 32,32,40,40,48,48")
    ap.add_argument("--crosscheck", action="store_true")
    ap.add_argument("--frontier", action="store_true", help="打印 面积(ΣP)-最大层周期 前沿；同时给出仅 RF<=n_in 家族的 ΣP 下限")
    a = ap.parse_args()
    ch = tuple(int(x) for x in a.widen.split(",")) if a.widen else (16, 16, 20, 20, 24, 24)
    L = table(layers(ch))
    print("层参数:", [(l["name"], l["n_in"], l["n_out"], l["px"], l["macs"]) for l in L])
    if a.frontier:
        print("仅 RF<=n_in 家族的 ΣP 下限 =", sum(l["n_out"] for l in L), "(= Σn_out；再低只能走 RF>n_in 分支)")
        cands = sorted({l["px"] * rf for l in L for rf in l["valid"]})
        last = None
        for T in cands:
            sel, P, ok = [], 0, True
            for l in L:
                c = [rf for rf in l["valid"] if l["px"] * rf <= T]
                if not c: ok = False; break
                rf = max(c); sel.append(rf); P += l["n_in"] * l["n_out"] // rf
            if ok and P != last and 20000 <= T <= 600000:
                last = P
                print(f"T<={T:7d} cyc ({T*5e-6:5.2f} ms)  ΣP={P:4d}  RF={sel}  branch={[dense_variant(l['n_in'], r)[3:] for l, r in zip(L, sel)]}")
        raise SystemExit
    if a.crosscheck:
        from hls4ml.backends import get_backend
        be = get_backend("Vivado")
        for l in L:
            assert be.get_valid_reuse_factors(l["n_in"], l["n_out"]) == l["valid"], l["name"]
        print("与 hls4ml.get_valid_reuse_factors 完全一致")
    if ch == (16, 16, 20, 20, 24, 24):
        report(L, "当前(P=4)", [108, 576, 720, 900, 1080, 1296])
        report(L, "A1' (RF=n_in, P=n_out)", [27, 144, 144, 180, 180, 216])
        print("\n用户文档 A1/A2 里不合法的 RF(会被 hls4ml 静默改成最近合法值):")
        for nm, rf in [("conv2a",180),("conv2b",225),("conv3a",270),("conv3b",324),("conv2a",60),("conv2b",75)]:
            l = next(x for x in L if x["name"] == nm)
            near = min(l["valid"], key=lambda v: (abs(v-rf), v))
            print(f"   {nm} RF={rf}: valid={valid_rf(l['n_in'], l['n_out'], rf)}  -> hls4ml 会改成 {near}")
    for budget in ((120, 190, 330, 480) if ch == (16,16,20,20,24,24) else (480, 640)):
        b = plan_balanced(L, budget)
        if b:
            T, sel, ptot = b
            report(L, f"均衡分配 P预算<={budget}", [rf for _, rf, _ in sel])
