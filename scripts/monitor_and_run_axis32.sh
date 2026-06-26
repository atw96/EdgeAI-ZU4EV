#!/bin/bash
# Monitor RTL cosim; on completion/failure launch axis32_out pipeline.
set -euo pipefail

REPO="/home/atw/Edge_AI_Acc/claude/EdgeAI-ZU4EV_Claude"
LOG="${REPO}/results/monitor_axis32.log"
COSIM_LOG="${REPO}/results/p1_rtl_cosim.log"
AXIS_LOG="${REPO}/results/axis32_out_pipeline.log"
STATUS_JSON="${REPO}/results/p1_rtl_cosim_status.json"

exec >> "$LOG" 2>&1
log() { echo "[$(date '+%F %T')] $*"; }

log "=== monitor_and_run_axis32 start ==="

# Wait for cosim process if still running (max 90 min)
WAIT_MAX=5400
WAITED=0
while pgrep -f 'vivado_hls.*cosim=1' >/dev/null 2>&1; do
    if (( WAITED >= WAIT_MAX )); then
        log "cosim wait timeout; proceeding"
        break
    fi
    log "cosim still running... (${WAITED}s)"
    sleep 60
    WAITED=$((WAITED + 60))
done

if [[ -f "$COSIM_LOG" ]]; then
    if grep -q 'COSIM 212-5' "$COSIM_LOG" 2>/dev/null; then
        log "cosim FAILED (linker) — documented in p1_rtl_cosim_status.json"
    elif grep -q 'rtl_cosim_results.log' "$COSIM_LOG" 2>/dev/null || \
         [[ -f "${REPO}/notebooks/hls4ml_prj/tb_data/rtl_cosim_results.log" ]]; then
        log "cosim appears SUCCESS"
    else
        log "cosim ended with unknown status; tail:"
        tail -5 "$COSIM_LOG"
    fi
else
    log "no cosim log found"
fi

if pgrep -f 'bash scripts/run_axis32_out_pipeline.sh' >/dev/null 2>&1; then
    log "axis32 pipeline already running — skip launch"
    exit 0
fi

log "Launching axis32_out_pipeline..."
cd "$REPO"
export OUTPUT_AXIS_BITS=32
export HLS_OUTPUT_AXIS_BITS=32
bash scripts/run_axis32_out_pipeline.sh

log "=== monitor_and_run_axis32 done ==="
