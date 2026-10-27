#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
# V3.2 steps a and b. Target host: wsl-local SSH to ${BOARD_IP:?BOARD_IP}.
# One SSH at a time. No DMA unless fpga0 is operating.
set -euo pipefail
REPO=${EDGEAI_ROOT}
IP=${BOARD_IP:?BOARD_IP}
SYN=$REPO/results/opt_v2/v5_synth
export SSHPASS="${SSHPASS:?SSHPASS}"
OPTS="-o ConnectTimeout=8 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ServerAliveInterval=15 -o ServerAliveCountMax=40"
LOG=$REPO/results/opt_v2/logs/v5_v32.log
mkdir -p "$REPO/results/opt_v2/logs"
exec > >(tee -a "$LOG") 2>&1
echo "[$(date '+%F %T')] v32 start"
if pgrep -af '${BOARD_IP:?BOARD_IP}' | grep -v "$$" | grep -v pgrep >/dev/null; then
  echo "another ssh is already running"
  exit 1
fi
source ${HOME}/miniconda3/etc/profile.d/conda.sh
conda activate edgeai_39
python3 - <<'PY'
import numpy as np
from pathlib import Path
repo = Path(__import__("os").environ["EDGEAI_ROOT"])
syn = repo / "results/opt_v2/v5_synth"
pack = np.load(syn / "synth_packed.npz", allow_pickle=True)
names = [str(x) for x in pack["names"]]
kat = np.load(syn / "kat_packed.npz")
def row(name):
    return np.asarray(pack["payloads"][names.index(name)])
np.savez(
    syn / "v32_frames.npz",
    black=row("gray_0"),
    white=row("extreme_111"),
    gray51=row("gray_51"),
    gray52=row("gray_52"),
    natural=np.asarray(kat["payloads"][0]),
)
print("v32 frames ready", names.index("gray_0"), names.index("gray_51"), names.index("gray_52"), names.index("extreme_111"))
PY
timeout 20 sshpass -e ssh $OPTS root@$IP 'cat /sys/class/fpga_manager/fpga0/state; mkdir -p /tmp/edgeai_bench'
timeout 40 sshpass -e scp $OPTS \
  "$REPO/scripts/dma_infer_common.py" \
  "$REPO/scripts/slot32_layout.py" \
  "$REPO/scripts/board_fix_hp0_width.py" \
  ${EDGEAI_ROOT}/scripts/opt_v2/v5_v32_ab.py \
  "$SYN/v32_frames.npz" \
  root@$IP:/tmp/edgeai_bench/
timeout 20 sshpass -e ssh $OPTS root@$IP 'cd /tmp/edgeai_bench && python3 board_fix_hp0_width.py'
STATE=$(timeout 20 sshpass -e ssh $OPTS root@$IP 'cat /sys/class/fpga_manager/fpga0/state')
echo "state [$STATE]"
if [ "$STATE" != "operating" ]; then
  echo "refuse DMA, PL is not operating"
  exit 1
fi
timeout 180 sshpass -e ssh $OPTS root@$IP 'cd /tmp/edgeai_bench && export OUT_DIM=24 OUT_BYTES=96 OUT_LAYOUT=gap_ps OUT_FIXED_SCALE=1024 OUTPUT_PACK_MODE=serial DMA_IOC_TIMEOUT_S=5 PYTHONUNBUFFERED=1 BENCH_NPZ=/tmp/edgeai_bench/v32_frames.npz && python3 v5_v32_ab.py'
timeout 30 sshpass -e ssh $OPTS root@$IP 'cd /tmp/edgeai_bench && tar cf - v32_raw.npz' | tar xf - -C "$SYN/"
echo "[$(date '+%F %T')] v32 fetched"
