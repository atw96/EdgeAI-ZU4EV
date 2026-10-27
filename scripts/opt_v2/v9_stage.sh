#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
# Compile the C harness, pack bins, and copy them to the board. No DMA, no clock write.
set -euo pipefail
H=${EDGEAI_ROOT}
M=${EDGEAI_ROOT}
STAGE=/tmp/v9_stage
IP=${BOARD_IP:?BOARD_IP}
export SSHPASS="${SSHPASS:?SSHPASS}"
OPTS="-o ConnectTimeout=8 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
LOG=$H/results/opt_v2/logs/v9_stage.log
mkdir -p "$H/results/opt_v2/logs" "$STAGE"
exec > >(tee -a "$LOG") 2>&1
echo "[$(date '+%F %T')] stage"
GCC=/tools/Xilinx/Vitis/2020.1/gnu/aarch64/lin/aarch64-linux/bin/aarch64-linux-gnu-gcc
for src in v8_x2_hot.c v8_x3.c; do
  sed 's/\r$//' "$H/scripts/opt_v2/$src" > "$STAGE/$src"
  "$GCC" -O2 -std=c11 -Wall -o "$STAGE/${src%.c}" "$STAGE/$src"
done
source ${HOME}/miniconda3/etc/profile.d/conda.sh
conda activate edgeai_39
python3 - << 'PY'
import numpy as np
from pathlib import Path
H = Path(__import__("os").environ["EDGEAI_ROOT"])
S = Path("/tmp/v9_stage")
bench = np.load(H / "results/opt_v2/bench10k_packed.npz")
key = "payloads" if "payloads" in bench.files else bench.files[0]
payloads = np.asarray(bench[key], dtype=np.uint8)
print("bench", key, payloads.shape, bench.files)
assert payloads.shape[1] == 6144
payloads.tofile(S / "bench_payloads.bin")
gap = np.load(H / "results/opt_v2/v5_v2/board_gap_v2_rc1.npy")
print("gap", gap.shape, gap.dtype)
lsb = gap.astype(np.int32)
lsb.tofile(S / "bench_golden.bin")
dense = np.load(H / "deploy/dense_head.npz")
w = np.asarray(dense["weight"] if "weight" in dense.files else dense["w"], dtype=np.float32)
b = np.asarray(dense["bias"] if "bias" in dense.files else dense["b"], dtype=np.float32)
print("dense", w.shape, b.shape, dense.files)
w.astype(np.float32).tofile(S / "dense_w.bin")
b.astype(np.float32).tofile(S / "dense_b.bin")
scores = (lsb.astype(np.float32) / 1024.0) @ w + b
top1 = scores.argmax(axis=1).astype(np.int32)
top1.tofile(S / "bench_top1.bin")
print("top1", top1.shape)
PY
cp -f "$H/results/opt_v2/a2l/cifar10_accel.bit" "$STAGE/cifar10_accel_a2l.bit"
cp -f "$H/deploy/opt_v2/A1shallow/cifar10_accel.bit" "$STAGE/cifar10_accel_rc1.bit"
cp -f "$H/deploy/cifar10_accel.bit" "$STAGE/cifar10_accel_old.bit"
sshpass -e ssh $OPTS root@$IP 'mkdir -p /tmp/edgeai_bench'
scp $OPTS \
  "$STAGE/v8_x2_hot" "$STAGE/v8_x3" \
  "$STAGE/bench_payloads.bin" "$STAGE/bench_golden.bin" "$STAGE/bench_top1.bin" \
  "$STAGE/dense_w.bin" "$STAGE/dense_b.bin" \
  "$STAGE/cifar10_accel_a2l.bit" "$STAGE/cifar10_accel_rc1.bit" "$STAGE/cifar10_accel_old.bit" \
  "$H/scripts/opt_v2/v8_x1.py" \
  "$H/scripts/dma_infer_common.py" \
  "$H/scripts/slot32_layout.py" \
  "$H/scripts/board_load_only.sh" \
  "$H/scripts/board_fix_hp0_width.py" \
  "$H/deploy/dense_head.npz" \
  "$H/results/opt_v2/bench10k_packed.npz" \
  "$H/results/opt_v2/v5_v2/board_gap_v2_rc1.npy" \
  "$H/results/opt_v2/v5_synth/kat_packed.npz" \
  "$H/results/opt_v2/v5_synth/kat_golden.npz" \
  root@$IP:/tmp/edgeai_bench/
sshpass -e ssh $OPTS root@$IP 'cd /tmp/edgeai_bench && chmod +x v8_x2_hot v8_x3 board_load_only.sh && md5sum cifar10_accel_a2l.bit cifar10_accel_rc1.bit cifar10_accel_old.bit && ls -l v8_x2_hot v8_x3'
echo STAGE_DONE
