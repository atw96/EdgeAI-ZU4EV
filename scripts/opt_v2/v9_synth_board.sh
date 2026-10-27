#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
set -euo pipefail
export SSHPASS="${SSHPASS:?SSHPASS}"
OPTS="-o ConnectTimeout=8 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ServerAliveInterval=5 -o ServerAliveCountMax=12"
IP=${BOARD_IP:?BOARD_IP}
H=${EDGEAI_ROOT}
S=/tmp/v9_stage
source ${HOME}/miniconda3/etc/profile.d/conda.sh
conda activate edgeai_39
python3 - << 'PY'
import numpy as np
from pathlib import Path
H = Path(__import__("os").environ["EDGEAI_ROOT"])
S = Path("/tmp/v9_stage")
pack = np.load(H / "results/opt_v2/v5_synth/synth_packed.npz")
payloads = np.asarray(pack["payloads"], dtype=np.uint8)
assert payloads.shape == (729, 6144)
payloads.tofile(S / "synth729_payloads.bin")
lines = (H / "results/opt_v2/v5_synth/csim_results.log").read_text().splitlines()
gap = np.array([[float(x) for x in ln.split()] for ln in lines if ln.strip()], dtype=np.float64)
assert gap.shape == (729, 24)
lsb = np.rint(gap * 1024.0).astype(np.int32)
lsb.tofile(S / "synth729_golden_rc1.bin")
dense = np.load(H / "deploy/dense_head.npz")
w = np.asarray(dense["weight"], dtype=np.float32)
b = np.asarray(dense["bias"], dtype=np.float32)
top1 = ((lsb.astype(np.float32) / 1024.0) @ w + b).argmax(axis=1).astype(np.int32)
top1.tofile(S / "synth729_top1.bin")
print("packed", payloads.shape, lsb.shape, top1.shape)
PY
for f in synth729_payloads.bin synth729_golden_rc1.bin synth729_top1.bin; do
  timeout 60 sshpass -e scp $OPTS "$S/$f" root@$IP:/tmp/edgeai_bench/
done
timeout 60 sshpass -e ssh $OPTS root@$IP 'cd /tmp/edgeai_bench && EXPECT_DIV0=10 python3 v8_x1.py readreg && md5sum /lib/firmware/cifar10_accel.bit && ./v8_x2_hot bench 729 synth729_payloads.bin synth729_golden_rc1.bin synth729_top1.bin dense_w.bin dense_b.bin'
echo SYNTH_BOARD_DONE
