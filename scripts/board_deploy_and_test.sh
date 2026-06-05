#!/bin/bash
# Deploy bit + scripts; force PL reload; run board_dma_verify.py
set -euo pipefail

REPO_WSL="/home/atw/Edge_AI_Acc/claude/EdgeAI-ZU4EV_Claude"
REPO_WIN="/mnt/e/WSL_ENV/project/EdgeAI-ZU4EV_Claude"
BOARD_IP="${BOARD_IP:-192.168.0.100}"
BOARD_USER="${BOARD_USER:-root}"
BOARD_PASS="${BOARD_PASS:-root}"
SSH_OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=20 -o ServerAliveInterval=5 -o ServerAliveCountMax=3 -o HostKeyAlgorithms=+ssh-rsa -o PubkeyAcceptedAlgorithms=+ssh-rsa"
RUN_DEVMEM_TESTS="${RUN_DEVMEM_TESTS:-0}"

log() { echo "[$(date '+%H:%M:%S')] $*"; }
run_ssh() { sshpass -p "${BOARD_PASS}" ssh ${SSH_OPTS} "${BOARD_USER}@${BOARD_IP}" "$@"; }

cd "${REPO_WSL}"
cp "${REPO_WIN}/scripts/board_"* "${REPO_WSL}/scripts/" 2>/dev/null || true

if [ ! -f deploy/cifar10_accel.bit ]; then
    log "ERROR: deploy/cifar10_accel.bit missing"
    exit 1
fi

log "=== Local bitstream ==="
ls -la deploy/cifar10_accel.bit
md5sum deploy/cifar10_accel.bit

log "=== Prepare board dirs ==="
ssh-keygen -f "${HOME}/.ssh/known_hosts" -R "${BOARD_IP}" 2>/dev/null || true
run_ssh 'mkdir -p /lib/firmware /root/firmware /root/scripts /tmp'

log "=== Upload bit + scripts ==="
sshpass -p "${BOARD_PASS}" scp ${SSH_OPTS} deploy/cifar10_accel.bit \
    "${BOARD_USER}@${BOARD_IP}:/root/firmware/cifar10_accel.bit"
sshpass -p "${BOARD_PASS}" scp ${SSH_OPTS} deploy/cifar10_accel.bit \
    "${BOARD_USER}@${BOARD_IP}:/lib/firmware/cifar10_accel.bit"
sshpass -p "${BOARD_PASS}" scp ${SSH_OPTS} \
    scripts/board_load_only.sh scripts/board_dma_verify.py scripts/board_infer.py \
    "${BOARD_USER}@${BOARD_IP}:/root/scripts/"
run_ssh 'cp -f /root/scripts/* /tmp/; chmod +x /tmp/board_load_only.sh'

log "=== Force PL reload ==="
run_ssh 'FORCE_PL_RELOAD=1 sh /tmp/board_load_only.sh'

if [ "${RUN_DEVMEM_TESTS}" = "1" ]; then
    log "=== DMA verify ==="
    run_ssh 'python3 -u /tmp/board_dma_verify.py' || log "WARN: DMA verify failed"
    log "=== Inference (optional) ==="
    run_ssh 'python3 -u /tmp/board_infer.py' || log "WARN: infer failed"
else
    log "SKIP devmem tests (set RUN_DEVMEM_TESTS=1 to run verify)"
fi

log "=== DONE ==="
