#!/bin/bash
# P0: deploy probe scripts to board, run experiments, fetch report + compare bit md5.
set -euo pipefail

BOARD_IP="${BOARD_IP:-192.168.1.40}"
BOARD_USER="${BOARD_USER:-root}"
BOARD_PASS="${BOARD_PASS:-root}"
REPO="$(cd "$(dirname "$0")/.." && pwd)"
LOG="${REPO}/results/p0_probe_run.log"

exec > >(tee -a "$LOG") 2>&1
log() { echo "[$(date '+%F %T')] $*"; }

log "=== P0 board probe automation ==="

WSL_MD5=""
if [[ -f "${REPO}/deploy/cifar10_accel.bit" ]]; then
    WSL_MD5=$(md5sum "${REPO}/deploy/cifar10_accel.bit" | awk '{print $1}')
    log "WSL deploy bit md5: ${WSL_MD5}"
fi

sshpass -p "$BOARD_PASS" ssh -o StrictHostKeyChecking=no "${BOARD_USER}@${BOARD_IP}" \
  "mkdir -p /tmp/edgeai_bench"

sshpass -p "$BOARD_PASS" scp -o StrictHostKeyChecking=no \
  "$REPO/scripts/board_p0_probe.py" \
  "$REPO/scripts/board_aa_prefill_test.py" \
  "$REPO/scripts/dma_infer_common.py" \
  "$REPO/deploy/cifar10_bench.npz" \
  "${BOARD_USER}@${BOARD_IP}:/tmp/edgeai_bench/"

log "--- Run board_p0_probe.py on board ---"
sshpass -p "$BOARD_PASS" ssh -o StrictHostKeyChecking=no "${BOARD_USER}@${BOARD_IP}" \
  "cd /tmp/edgeai_bench && P0_REPORT_JSON=p0_probe_report.json python3 -u board_p0_probe.py" \
  | tee "${REPO}/results/p0_probe_board.log"

sshpass -p "$BOARD_PASS" scp -o StrictHostKeyChecking=no \
  "${BOARD_USER}@${BOARD_IP}:/tmp/edgeai_bench/p0_probe_report.json" \
  "${REPO}/results/p0_probe_report.json"

log "--- Re-run AA prefill (fixed verdict) ---"
sshpass -p "$BOARD_PASS" ssh -o StrictHostKeyChecking=no "${BOARD_USER}@${BOARD_IP}" \
  "cd /tmp/edgeai_bench && python3 -u board_aa_prefill_test.py" \
  | tee "${REPO}/results/p0_aa_prefill_rerun.log"

python3 - <<PY
import json
from pathlib import Path
repo = Path("${REPO}")
report_path = repo / "results" / "p0_probe_report.json"
r = json.loads(report_path.read_text())
wsl = "${WSL_MD5}" or None
r["wsl_bit_md5"] = wsl
board_md5 = r.get("p0_5_bit", {}).get("board_bit_md5")
r["bit_md5_match"] = bool(wsl and board_md5 and wsl == board_md5)
if wsl and board_md5 and wsl != board_md5:
    p2 = {"conclusion": "bit_deploy_mismatch", "actions": ["Fix deploy/reload"]}
elif r.get("p0_3_input_variation", {}).get("logits_0_3_identical"):
    p2 = {"conclusion": "input_path_broken", "actions": ["Pause output fixes; debug MM2S input"]}
else:
    slen = r.get("p0_1_s2mm_len", {}).get("s2mm_len_reg")
    if slen == 8:
        p2 = {"conclusion": "mechanism_B_early_tlast", "actions": ["head-Latency or fix HLS beat count"]}
    elif slen == 20:
        p2 = {"conclusion": "mechanism_A_wstrb_or_stale_dram", "actions": ["axis32_out or ILA TKEEP"]}
    else:
        p2 = {"conclusion": "inconclusive", "actions": ["Run P1 cosim"]}
    if r.get("p0_4_queue", {}).get("s2mm_only_ioc"):
        p2.setdefault("actions", []).append("Queue probe positive")
r["p2_decision"] = p2
report_path.write_text(json.dumps(r, indent=2))
print(json.dumps(r, indent=2))
PY

log "=== P0 complete. Report: results/p0_probe_report.json ==="
