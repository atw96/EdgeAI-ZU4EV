#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
set -euo pipefail
REPO=${EDGEAI_ROOT}
IP=${BOARD_IP:?BOARD_IP}
export SSHPASS="${SSHPASS:?SSHPASS}"
OPTS="-o ConnectTimeout=8 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ServerAliveInterval=15"
cd "$REPO"
timeout 60 sshpass -e ssh $OPTS root@${IP} 'cd /tmp/edgeai_bench && tar cf - board_gap_reset_each.npy board_pred_reset_each.npy board_lat_reset_each.npy board_gap_no_reset.npy board_pred_no_reset.npy board_lat_no_reset.npy board_gap_rep1.npy' | tar xf - -C results/opt_v2/
source ${HOME}/miniconda3/etc/profile.d/conda.sh
conda activate edgeai_39
python3 - <<'PY'
import json
from pathlib import Path
import numpy as np
repo = Path(__import__("os").environ["EDGEAI_ROOT"])
out = repo / 'results' / 'opt_v2'
gap = np.load(out / 'board_gap_reset_each.npy')
pred = np.load(out / 'board_pred_reset_each.npy')
lat = np.load(out / 'board_lat_reset_each.npy')
nr = np.load(out / 'board_gap_no_reset.npy')
nrp = np.load(out / 'board_pred_no_reset.npy')
nrl = np.load(out / 'board_lat_no_reset.npy')
rep = np.load(out / 'board_gap_rep1.npy')
y = np.load(out / 'v4_labels_10k.npy')
kp = np.load(out / 'v4_keras_pred_10k.npy')
kg = np.load(out / 'v4_keras_gap_10k.npy')
n = min(len(gap), len(y), len(pred))
top_b = 100.0 * float(np.mean(pred[:n] == y[:n]))
top_k = 100.0 * float(np.mean(kp[:n] == y[:n]))
top_nr = 100.0 * float(np.mean(nrp[:n] == y[:n]))
lsb_nr = int(np.max(np.abs(gap.astype(np.int32) - nr.astype(np.int32))))
lsb_rep = int(np.max(np.abs(gap[:len(rep)].astype(np.int32) - rep.astype(np.int32))))
# csim prefix
lines = (repo / 'notebooks/hls4ml_prj/tb_data/csim_results.log').read_text().splitlines()
m = min(len(lines), n)
csim = np.array([[float(x) for x in lines[i].split()] for i in range(m)])
csim_lsb = np.rint(csim * 1024.0).astype(np.int32)
board_lsb = gap[:m].astype(np.int32)
lsb_c = int(np.max(np.abs(board_lsb - csim_lsb)))
# keras gap mae on board, in the same units as the 1000-image gate
mae = float(np.mean(np.abs(gap.astype(np.float64) / 1024.0 - kg[:n])))
doc = {
    'n': int(n),
    'board_top1_reset_each': top_b,
    'board_top1_no_reset': top_nr,
    'keras_top1': top_k,
    'top1_gap_pt': top_k - top_b,
    'gap_lsb_reset_vs_no_reset': lsb_nr,
    'gap_lsb_reset_vs_rep1': lsb_rep,
    'csim_prefix': m,
    'gap_lsb_board_vs_csim_prefix': lsb_c,
    'mae_board_vs_keras_gap': mae,
    'lat_reset_median_ms': float(np.median(lat)),
    'lat_reset_p99_ms': float(np.percentile(lat, 99)),
    'lat_no_reset_median_ms': float(np.median(nrl)),
    'lat_no_reset_p99_ms': float(np.percentile(nrl, 99)),
    'aa_frames': 0,
}
print(json.dumps(doc, indent=2))
(out / 'v4_board_10k_summary.json').write_text(json.dumps(doc, indent=2), encoding='utf-8')
# snapped floats for e2e, prefix = all csim lines we have
np.save(out / 'v4_board_gap_f.npy', (gap.astype(np.float64) / 1024.0))
np.save(out / 'v4_csim_gap_prefix_f.npy', (csim_lsb.astype(np.float64) / 1024.0))
PY
echo ANALYZED
