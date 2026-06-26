import json
from pathlib import Path

repo = Path("/home/atw/Edge_AI_Acc/claude/EdgeAI-ZU4EV_Claude")
line = (repo / "notebooks/hls4ml_prj/tb_data/csim_results.log").read_text().strip().split()
vals = [float(x) for x in line[:10]]
out = {
    "csim_ok": True,
    "output10": [round(v, 4) for v in vals],
    "mid4": [round(v, 4) for v in vals[4:8]],
    "mid4_all_zero": all(abs(v) < 1e-6 for v in vals[4:8]),
}
(repo / "results/strategy_csim_result.json").write_text(json.dumps(out, indent=2))
print(json.dumps(out, indent=2))
