#!/bin/bash
# Sync Windows project mount -> Ubuntu-18.04 WSL home repo (run as user atw).
set -euo pipefail

REPO_WSL="/home/atw/Edge_AI_Acc/claude/EdgeAI-ZU4EV_Claude"
REPO_WIN="/mnt/e/WSL_ENV/project/EdgeAI-ZU4EV_Claude"

EXCLUDES=(
    --exclude=.git
    --exclude=vivado_project
    --exclude=vivado_project.backup.*
    --exclude=*.jou
    --exclude=*.log
    --exclude=__pycache__
    --exclude=.specstory
)

log() { echo "[sync $(date '+%H:%M:%S')] $*"; }

if [ ! -d "${REPO_WIN}" ]; then
    echo "ERROR: Windows mount missing: ${REPO_WIN}"
    exit 1
fi

mkdir -p "${REPO_WSL}"

log "WIN -> WSL"
log "  src: ${REPO_WIN}"
log "  dst: ${REPO_WSL}"

rsync -a "${EXCLUDES[@]}" \
    "${REPO_WIN}/" "${REPO_WSL}/"

log "done. WSL repo ready at ${REPO_WSL}"
