#!/usr/bin/env bash
set -euo pipefail
BOARD="${BOARD_IP:-192.168.0.100}"
SSH_OPTS=(-o StrictHostKeyChecking=no -o HostKeyAlgorithms=+ssh-rsa)
WHEEL_URL="https://github.com/google-coral/pycoral/releases/download/v2.0.0/tflite_runtime-2.5.0.post1-cp37-cp37m-linux_aarch64.whl"
WHEEL="/tmp/tflite_runtime-2.5.0-cp37-cp37m-linux_aarch64.whl"

echo "[1] Download wheel in WSL"
curl -fsSL -o "$WHEEL" "$WHEEL_URL" || {
  echo "cp37 wheel missing, try PyPI index..."
  curl -fsSL -o "$WHEEL" "https://files.pythonhosted.org/packages/source/t/tflite-runtime/tflite_runtime-2.5.0.post1-cp37-cp37m-linux_aarch64.whl" || exit 1
}

echo "[2] SCP wheel to board"
sshpass -p root scp "${SSH_OPTS[@]}" "$WHEEL" "root@${BOARD}:/tmp/tflite_runtime.whl"

echo "[3] Install on board (manual wheel extract if pip missing)"
sshpass -p root ssh "${SSH_OPTS[@]}" "root@${BOARD}" <<'REMOTE'
set -e
W=/tmp/tflite_runtime.whl
if python3 -m pip --version >/dev/null 2>&1; then
  python3 -m pip install --no-cache-dir "$W"
else
  python3 - <<'PY'
import zipfile, os, shutil
wheel = "/tmp/tflite_runtime.whl"
site = "/usr/lib/python3.7/site-packages"
with zipfile.ZipFile(wheel) as z:
    for name in z.namelist():
        if name.endswith("/"):
            continue
        if ".data/purelib/" in name:
            rel = name.split(".data/purelib/", 1)[1]
        elif ".dist-info/" in name:
            rel = name
        else:
            continue
        target = os.path.join(site, rel)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with z.open(name) as src, open(target, "wb") as dst:
            shutil.copyfileobj(src, dst)
print("manual wheel install ->", site)
PY
fi
python3 -c "import tflite_runtime; print('tflite_runtime OK')"
REMOTE

echo "[4] Re-run PLAN A baseline"
sshpass -p root ssh "${SSH_OPTS[@]}" "root@${BOARD}" 'cd /root && python3 cpu_baseline.py'

REPO_WSL="/home/atw/Edge_AI_Acc/claude/EdgeAI-ZU4EV_Claude"
mkdir -p "$REPO_WSL/results"
sshpass -p root scp "${SSH_OPTS[@]}" "root@${BOARD}:/root/results/cpu_baseline.json" "$REPO_WSL/results/cpu_baseline.json"
cp "$REPO_WSL/results/cpu_baseline.json" /mnt/e/WSL_ENV/project/EdgeAI-ZU4EV_Claude/results/cpu_baseline.json
echo "[DONE]"
cat /mnt/e/WSL_ENV/project/EdgeAI-ZU4EV_Claude/results/cpu_baseline.json
