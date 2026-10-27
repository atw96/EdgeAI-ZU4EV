#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
set -euo pipefail
REPO=${EDGEAI_ROOT}
IP=${BOARD_IP:?BOARD_IP}
export SSHPASS="${SSHPASS:?SSHPASS}"
OPTS="-o ConnectTimeout=8 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ServerAliveInterval=15"
cd "$REPO"
source ${HOME}/miniconda3/etc/profile.d/conda.sh
conda activate edgeai_39
python3 ${EDGEAI_ROOT}/docs/e2e_compare.py \
  --labels results/opt_v2/v4_labels_10k.npy \
  --keras-pred results/opt_v2/v4_keras_pred_10k.npy \
  --board-pred results/opt_v2/board_pred_reset_each.npy \
  --board-gap results/opt_v2/v4_board_gap_f.npy \
  --csim-gap results/opt_v2/v4_csim_gap_prefix_f.npy \
  --lat-ms results/opt_v2/board_lat_reset_each.npy \
  --out results/opt_v2/e2e_report.json || echo E2E_FAIL

# PL must still be operating. One SSH, then the short DMA runs.
STATE=$(timeout 20 sshpass -e ssh $OPTS root@$IP 'cat /sys/class/fpga_manager/fpga0/state')
echo "state $STATE"
if [ "$STATE" != "operating" ]; then
  echo "refuse DMA"
  exit 2
fi
timeout 30 sshpass -e scp $OPTS "$REPO/results/opt_v2/bench_extreme.npz" root@$IP:/tmp/edgeai_bench/bench_extreme.npz
timeout 180 sshpass -e ssh $OPTS root@$IP 'cd /tmp/edgeai_bench && export OUT_DIM=24 OUT_BYTES=96 OUT_LAYOUT=gap_ps OUT_FIXED_SCALE=1024 OUTPUT_PACK_MODE=serial DENSE_NPZ=/tmp/edgeai_bench/dense_head.npz DMA_IOC_TIMEOUT_S=5 PYTHONUNBUFFERED=1 && export BENCH_NPZ=/tmp/edgeai_bench/bench_extreme.npz N_BOARD=4 RESET_EACH=1 BOARD_TAG=extreme && python3 board_10k.py && export BENCH_NPZ=/tmp/edgeai_bench/bench10k_packed.npz N_BOARD=200 BOARD_TAG=rep2 && python3 board_10k.py && export N_BOARD=200 BOARD_TAG=rep3 && python3 board_10k.py'
timeout 30 sshpass -e ssh $OPTS root@$IP 'cd /tmp/edgeai_bench && tar cf - board_gap_extreme.npy board_gap_rep2.npy board_gap_rep3.npy' | tar xf - -C results/opt_v2/
python3 - <<'PY'
import numpy as np
from pathlib import Path
repo = Path(__import__("os").environ["EDGEAI_ROOT"])
out = repo / 'results' / 'opt_v2'
ext = np.load(out / 'board_gap_extreme.npy').astype(np.float64) / 1024.0
ker = np.load(out / 'v4_keras_gap_extreme.npy').astype(np.float64)
d = np.abs(ext - ker)
lsb = np.abs(np.rint(ext * 1024.0) - np.rint(ker * 1024.0))
print('extreme max_abs', float(d.max()), 'max_lsb', float(lsb.max()))
base = np.load(out / 'board_gap_reset_each.npy')
for name in ('rep2', 'rep3'):
    g = np.load(out / ('board_gap_%s.npy' % name))
    print(name, 'max_lsb', int(np.max(np.abs(base[:len(g)].astype(np.int32) - g.astype(np.int32)))))
PY
echo EXTREME_DONE
