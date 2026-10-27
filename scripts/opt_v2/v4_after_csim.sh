#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
# Wait for the 10k csim, then close D3, refresh the e2e prefix, and csim the 4 extremes.
set -euo pipefail
REPO=${EDGEAI_ROOT}
W=${EDGEAI_ROOT}
cd "$REPO"
LOG=$REPO/results/opt_v2/logs/v4_after_csim.log
exec > >(tee -a "$LOG") 2>&1
echo "[$(date '+%F %T')] waiting for v4_csim_10k.sh"
while pgrep -f 'scripts/opt_v2/v4_csim_10k.sh' >/dev/null; do
  sleep 60
done
echo "[$(date '+%F %T')] csim script exited"
if [ ! -f "$REPO/results/opt_v2/v4_csim_10k.log" ]; then
  echo "missing 10k log"
  exit 1
fi
wc -l "$REPO/results/opt_v2/v4_csim_10k.log"
source ${HOME}/miniconda3/etc/profile.d/conda.sh
conda activate edgeai_39
python3 - <<'PY'
import json
from pathlib import Path
import numpy as np
repo = Path(__import__("os").environ["EDGEAI_ROOT"])
out = repo / 'results' / 'opt_v2'
lines = (out / 'v4_csim_10k.log').read_text().splitlines()
csim = np.array([[float(x) for x in line.split()] for line in lines], dtype=np.float64)
lsb = np.rint(csim * 1024.0).astype(np.int32)
np.save(out / 'v4_csim_gap_prefix_f.npy', lsb.astype(np.float64) / 1024.0)
gap = np.load(out / 'board_gap_reset_each.npy').astype(np.int32)
m = min(len(gap), len(lsb))
print('full compare', m, 'max_lsb', int(np.max(np.abs(gap[:m] - lsb[:m]))))
PY
python3 "$W/scripts/opt_v2/v4_e2e_fallback.py"
# D3 record in the appendix schema. p1 json is written by v4_csim_10k.sh.
python3 - <<'PY'
import json
from pathlib import Path
repo = Path(__import__("os").environ["EDGEAI_ROOT"])
out = repo / 'results' / 'opt_v2'
p1 = json.loads((out / 'v4_d3_csim10k.json').read_text())
delta = abs(p1['top1_a1'] - p1['top1_keras'])
doc = {
    'id': 'D3',
    'date': '2026-10-17',
    'env': {'hls4ml': '1.3.0', 'vivado_hls': '2020.1'},
    'inputs': {'n_images': p1['n'], 'order': 'fixed test order, cifar10_bench_10k.npz',
               'log': 'results/opt_v2/v4_csim_10k.log'},
    'results': p1,
    'decision': '1 万张窄精度 csim Top-1 %.2f，Keras %.2f，差 %.2f 个点。G1 的 0.5 点门%s。MAE %.4f。' % (
        p1['top1_a1'], p1['top1_keras'], delta,
        '通过' if delta <= 0.5 and p1['mae_a1'] <= 0.03 else '未通过',
        p1['mae_a1']),
    'next': '这是部署候选的 csim 精度。不回到 BIT_EXACT=1。',
}
(out / 'v4_d3.json').write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding='utf-8')
print(doc['decision'])
PY

echo "[$(date '+%F %T')] extreme csim"
export SKIP_BOARD=1 OPT_V2_KEEP_RF=1
export N_GAP_COMPARE=4
export CSIM_NPZ=$REPO/results/opt_v2/bench_extreme.npz
bash scripts/run_gap_axi_csim.sh
cp -f notebooks/hls4ml_prj/tb_data/csim_results.log "$REPO/results/opt_v2/v4_csim_extreme.log"
python3 - <<'PY'
import numpy as np
from pathlib import Path
repo = Path(__import__("os").environ["EDGEAI_ROOT"])
out = repo / 'results' / 'opt_v2'
lines = (out / 'v4_csim_extreme.log').read_text().splitlines()
csim = np.array([[float(x) for x in line.split()] for line in lines[:4]])
board = np.load(out / 'board_gap_extreme.npy').astype(np.float64) / 1024.0
ker = np.load(out / 'v4_keras_gap_extreme.npy').astype(np.float64).reshape(4, -1)
lsb_b = np.max(np.abs(np.rint(csim * 1024) - np.rint(board * 1024)))
lsb_k = np.max(np.abs(np.rint(csim * 1024) - np.rint(ker[:, :24] * 1024)))
print('extreme csim vs board max_lsb', float(lsb_b))
print('extreme csim vs keras max_lsb', float(lsb_k))
(out / 'v4_extreme_csim.txt').write_text(
    'csim_vs_board_max_lsb %s\ncsim_vs_keras_max_lsb %s\n' % (lsb_b, lsb_k), encoding='utf-8')
PY
cp -f "$REPO/results/opt_v2/v4_d3.json" "$W/results/opt_v2/v4_d3.json" || true
cp -f "$REPO/results/opt_v2/e2e_report.json" "$W/results/opt_v2/e2e_report.json" || true
cp -f "$REPO/results/opt_v2/v4_extreme_csim.txt" "$W/results/opt_v2/v4_extreme_csim.txt" || true
echo "[$(date '+%F %T')] after_csim done"
