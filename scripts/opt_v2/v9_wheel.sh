#!/bin/bash
set -uo pipefail
URL="https://github.com/google-coral/pycoral/releases/download/v2.0.0/tflite_runtime-2.5.0.post1-cp37-cp37m-linux_aarch64.whl"
OUT=${HOME}/tflite_runtime-cp37-aarch64.whl
curl -fL --retry 2 -o "$OUT" "$URL"
echo CURL_RC $?
ls -l "$OUT"
