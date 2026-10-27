#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
# Finish the 10k csim from line 9539, then D3, full e2e, and the 4 extreme frames.
# Target host: wsl-local. Does not touch the board.
set -euo pipefail
REPO=${EDGEAI_ROOT}
HLS=$REPO/notebooks/hls4ml_prj
TB=$HLS/tb_data
BUILD=$HLS/myproject_prj/solution1/csim/build
OUT=$REPO/results/opt_v2
W=${EDGEAI_ROOT}
LOG=$OUT/logs/v4_resume_csim.log
mkdir -p "$OUT/logs"
exec > >(tee -a "$LOG") 2>&1
echo "[$(date '+%F %T')] resume"

HAVE=$(wc -l < "$TB/csim_results.log")
echo "have $HAVE"
if [ "$HAVE" -lt 9000 ]; then
  echo "partial log too short"
  exit 1
fi
cp -f "$TB/csim_results.log" "$OUT/v4_csim_10k_partial.log"
if [ ! -f "$TB/tb_input_features.dat.full10k" ]; then
  cp -f "$TB/tb_input_features.dat" "$TB/tb_input_features.dat.full10k"
  cp -f "$TB/tb_output_predictions.dat" "$TB/tb_output_predictions.dat.full10k"
fi
tail -n +$((HAVE + 1)) "$TB/tb_input_features.dat.full10k" > "$TB/tb_input_features.dat"
tail -n +$((HAVE + 1)) "$TB/tb_output_predictions.dat.full10k" > "$TB/tb_output_predictions.dat"
echo "remaining input $(wc -l < "$TB/tb_input_features.dat") pred $(wc -l < "$TB/tb_output_predictions.dat")"
if [ ! -x "$BUILD/csim.exe" ]; then
  echo "csim.exe missing"
  exit 1
fi
if [ ! -e "$BUILD/tb_data" ]; then
  ln -s "$TB" "$BUILD/tb_data"
fi
source /tools/Xilinx/Vivado/2020.1/settings64.sh
cd "$BUILD"
./csim.exe
REST=$(wc -l < "$TB/csim_results.log")
echo "resume wrote $REST"
cat "$OUT/v4_csim_10k_partial.log" "$TB/csim_results.log" > "$OUT/v4_csim_10k.log"
echo "combined $(wc -l < "$OUT/v4_csim_10k.log")"
cp -f "$TB/tb_input_features.dat.full10k" "$TB/tb_input_features.dat"
cp -f "$TB/tb_output_predictions.dat.full10k" "$TB/tb_output_predictions.dat"

source ${HOME}/miniconda3/etc/profile.d/conda.sh
conda activate edgeai_39
export PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python
export P1_GATE_JSON=$OUT/v4_d3_csim10k.json
export N_GAP_COMPARE=10000
export CSIM_NPZ=$REPO/deploy/cifar10_bench_10k.npz
rm -f "$P1_GATE_JSON"
python3 -u "$REPO/scripts/opt_v2/p1_numeric.py" "$OUT/v4_csim_10k.log" "$OUT/v4_csim_10k.log"

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
print('board vs csim', m, 'max_lsb', int(np.max(np.abs(gap[:m] - lsb[:m]))))
p1 = json.loads((out / 'v4_d3_csim10k.json').read_text())
delta = abs(p1['top1_a1'] - p1['top1_keras'])
doc = {
    'id': 'D3',
    'date': '2026-10-18',
    'env': {'hls4ml': '1.3.0', 'vivado_hls': '2020.1'},
    'inputs': {
        'n_images': p1['n'],
        'order': 'fixed test order, cifar10_bench_10k.npz',
        'log': 'results/opt_v2/v4_csim_10k.log',
        'note': 'csim.exe was killed at 9538 lines; the tail was rerun and concatenated',
    },
    'results': p1,
    'decision': '1 万张窄精度 csim Top-1 %.2f，Keras %.2f，差 %.2f 个点。MAE %.4f。0.5 点门%s。' % (
        p1['top1_a1'], p1['top1_keras'], delta, p1['mae_a1'],
        '通过' if delta <= 0.5 and p1['mae_a1'] <= 0.03 else '未通过'),
    'next': '这是部署候选的 csim 精度。不回到 BIT_EXACT=1。',
}
(out / 'v4_d3.json').write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding='utf-8')
print(doc['decision'])
PY
python3 "$REPO/scripts/opt_v2/v4_e2e_fallback.py" || python3 "$W/scripts/opt_v2/v4_e2e_fallback.py"

echo "[$(date '+%F %T')] extreme csim"
python3 - <<'PY'
import numpy as np
from pathlib import Path
repo = Path(__import__("os").environ["EDGEAI_ROOT"])
tb = repo / 'notebooks/hls4ml_prj/tb_data'
data = np.load(repo / 'results/opt_v2/bench_extreme.npz')
mat = data['payloads']
lines = []
for i in range(len(mat)):
    x = np.frombuffer(mat[i].tobytes(), dtype=np.int16).astype(np.float32) / 1024.0
    lines.append(' '.join(str(float(v)) for v in x))
text = '\n'.join(lines) + '\n'
(tb / 'tb_input_features.dat').write_text(text)
(tb / 'tb_output_predictions.dat').write_text(text)
print('extreme lines', len(lines))
PY
cd "$BUILD"
./csim.exe
cp -f "$TB/csim_results.log" "$OUT/v4_csim_extreme.log"
cp -f "$TB/tb_input_features.dat.full10k" "$TB/tb_input_features.dat"
cp -f "$TB/tb_output_predictions.dat.full10k" "$TB/tb_output_predictions.dat"
python3 - <<'PY'
import numpy as np
from pathlib import Path
repo = Path(__import__("os").environ["EDGEAI_ROOT"])
out = repo / 'results' / 'opt_v2'
lines = (out / 'v4_csim_extreme.log').read_text().splitlines()
csim = np.array([[float(x) for x in line.split()] for line in lines[:4]])
board = np.load(out / 'board_gap_extreme.npy').astype(np.float64) / 1024.0
ker = np.load(out / 'v4_keras_gap_extreme.npy').astype(np.float64).reshape(4, -1)[:, :24]
names = ['black', 'white', 'checker', 'sat']
lsb_b = np.max(np.abs(np.rint(csim * 1024) - np.rint(board * 1024)), axis=1)
lsb_k = np.max(np.abs(np.rint(csim * 1024) - np.rint(ker * 1024)), axis=1)
for i, name in enumerate(names):
    print(name, 'csim_vs_board_lsb', float(lsb_b[i]), 'csim_vs_keras_lsb', float(lsb_k[i]))
(out / 'v4_extreme_csim.txt').write_text(
    '\n'.join('%s board %s keras %s' % (n, b, k) for n, b, k in zip(names, lsb_b, lsb_k)) + '\n',
    encoding='utf-8')
PY
cp -f "$OUT/v4_d3.json" "$OUT/e2e_report.json" "$OUT/v4_extreme_csim.txt" "$OUT/v4_d3_csim10k.json" "$W/results/opt_v2/" || true
echo "[$(date '+%F %T')] resume done"
