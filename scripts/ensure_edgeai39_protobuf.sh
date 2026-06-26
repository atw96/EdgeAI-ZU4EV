#!/bin/bash
# TF 2.6 (edgeai_39) requires protobuf 3.20.x — protobuf 4.x breaks load_model.
set -euo pipefail

need_fix=0
python3 - <<'PY' || need_fix=1
import google.protobuf
v = google.protobuf.__version__
if not v.startswith('3.'):
    raise SystemExit(1)
PY

if [[ "$need_fix" -eq 1 ]]; then
  echo "[ensure_edgeai39_protobuf] installing protobuf==3.20.3 (TF2.6 compat)"
  pip install -q 'protobuf==3.20.3'
fi

export PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python
