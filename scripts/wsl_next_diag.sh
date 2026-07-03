#!/usr/bin/env bash
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
BOARD_IP="${BOARD_IP:?Set BOARD_IP before running}"
BOARD_USER="${BOARD_USER:-root}"
BOARD_PASS="${BOARD_PASS:-root}"
BOARD_DIR="/tmp/edgeai_bench"
CSIM_BEATS="${REPO}/notebooks/hls4ml_prj/tb_data/csim_axis_beats.log"

SERIAL_ENV="OUTPUT_AXIS_BITS=32 OUTPUT_PACK_MODE=serial AXI_DATAFLOW=0 OUT_DIM=24 OUT_BYTES=96 OUT_LAYOUT=gap_ps OUT_FIXED_SCALE=1024 IN_FIXED_SCALE=1024"

SSH_OPTS=(-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR)
ssh_board() { sshpass -p "${BOARD_PASS}" ssh "${SSH_OPTS[@]}" "${BOARD_USER}@${BOARD_IP}" "$@"; }
scp_board() { sshpass -p "${BOARD_PASS}" scp "${SSH_OPTS[@]}" "$@"; }

section() { echo ""; echo "========== $* =========="; }

activate_conda() {
  if [[ -f "${HOME}/miniconda3/etc/profile.d/conda.sh" ]]; then
    source "${HOME}/miniconda3/etc/profile.d/conda.sh"
  elif [[ -f "/opt/conda/etc/profile.d/conda.sh" ]]; then
    source "/opt/conda/etc/profile.d/conda.sh"
  fi
  conda activate edgeai_39
}

guard_dir() {
  if [[ -f "${REPO}/mcp-path-env-guard/server.py" ]]; then
    echo "${REPO}/mcp-path-env-guard"
  else
    echo "/mnt/e/WSL_ENV/project/EdgeAI-ZU4EV_Claude/mcp-path-env-guard"
  fi
}

cd "${REPO}"
activate_conda
ssh-keygen -f "${HOME}/.ssh/known_hosts" -R "${BOARD_IP}" 2>/dev/null || true

section "1) path-env-guard"
GUARD="$(guard_dir)"
export MCP_CONFIG="${GUARD}/config.yaml"
python3 - <<PY
import json, os, sys, importlib.util
guard = """${GUARD}"""
os.environ["MCP_CONFIG"] = guard + "/config.yaml"
spec = importlib.util.spec_from_file_location("guard_server", guard + "/server.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
repo = """${REPO}"""
board = """${BOARD_IP}"""
for name, fn, kwargs in [
    ("check_host_context", mod.tool_check_host_context, {}),
    ("verify_deploy_artifacts", mod.tool_verify_deploy_artifacts, {"project_root": repo}),
    ("verify_board_ssh", mod.tool_verify_board_ssh, {"board_ip": board, "user": "root"}),
]:
    out = fn(**kwargs)
    print("--- %s ---" % name)
    print(json.dumps(out, indent=2))
PY

section "2) deploy bit md5 + bd_create.log width"
md5sum "${REPO}/deploy/cifar10_accel.bit"
echo "--- bd_create.log (32-bit output / dwidth) ---"
grep -E '32-bit output|dwidth' "${REPO}/bd_create.log" || true

section "3) scp bench scripts to board"
ssh_board "mkdir -p ${BOARD_DIR}"
scp_board \
  "${REPO}/scripts/dma_infer_common.py" \
  "${REPO}/scripts/slot32_layout.py" \
  "${REPO}/scripts/board_fetch_gap.py" \
  "${REPO}/scripts/board_s2mm_scan.py" "${REPO}/scripts/board_aa_serial96_diag.py" \
  "${BOARD_USER}@${BOARD_IP}:${BOARD_DIR}/"
if [[ -f "${REPO}/deploy/cifar10_bench.npz" ]]; then
  scp_board "${REPO}/deploy/cifar10_bench.npz" "${BOARD_USER}@${BOARD_IP}:${BOARD_DIR}/"
fi

section "4) board firmware bit md5"
ssh_board "md5sum /lib/firmware/cifar10_accel.bit 2>/dev/null || md5sum /home/root/cifar10_accel.bit 2>/dev/null || echo bit_not_found"

section "5) AA prefill 96B serial env"
ssh_board "cd ${BOARD_DIR} && env BENCH_NPZ=${BOARD_DIR}/cifar10_bench.npz ${SERIAL_ENV} python3 -u board_aa_serial96_diag.py"

section "6) S2MM_LEN_OVERRIDE=128 board_s2mm_scan"
ssh_board "cd ${BOARD_DIR} && BENCH_NPZ=${BOARD_DIR}/cifar10_bench.npz S2MM_LEN_OVERRIDE=128 python3 -u board_s2mm_scan.py"

section "7) board_fetch_gap vs csim line 0"
BOARD_JSON_FILE="$(mktemp)"
ssh_board "cd ${BOARD_DIR} && env BENCH_NPZ=${BOARD_DIR}/cifar10_bench.npz SAMPLE_IDX=0 ${SERIAL_ENV} python3 -u board_fetch_gap.py" | tail -1 > "${BOARD_JSON_FILE}"
echo "board_fetch_gap: $(cat "${BOARD_JSON_FILE}")"

python3 - "${BOARD_JSON_FILE}" <<'PY'
import json, struct, sys
from pathlib import Path
board = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
raw = bytes.fromhex(board["raw_hex"])
board_words = [struct.unpack_from("<I", raw, w * 4)[0] for w in range(24)]
csim_path = Path("""${CSIM_BEATS}""")
line0 = csim_path.read_text(encoding="utf-8").strip().splitlines()[0]
csim_words = [int(x, 16) for x in line0.split()]
matches = sum(1 for i in range(24) if board_words[i] == csim_words[i])
print("match_count:", matches, "/ 24")
for i in range(24):
    bw, cw = board_words[i], csim_words[i]
    tag = "MATCH" if bw == cw else "DIFF"
    note = ""
    if bw == 0: note = " board=ZERO"
    elif bw == 0xAAAAAAAA: note = " board=AA"
    print("beat%02d %s board=%08x csim=%08x%s" % (i, tag, bw, cw, note))
print("board zero beats:", [i for i,w in enumerate(board_words) if w==0])
print("board AA beats:", [i for i,w in enumerate(board_words) if w==0xAAAAAAAA])
if matches >= 20:
    print("CONCLUSION: 24-beat serial DRAM matches csim; not slot-hole timing")
elif matches > 8:
    print("CONCLUSION: partial match — slot-hole / alignment or stale bit")
else:
    print("CONCLUSION: poor match — slot-hole timing or wrong PL/bit")
PY

section "done"