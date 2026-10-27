#!/bin/bash
: "${EDGEAI_ROOT:=$(cd "$(dirname "$0")/../.." && pwd)}"
export EDGEAI_ROOT
H=${EDGEAI_ROOT}
echo ----BIT----
md5sum "$H/deploy/cifar10_accel.bit" "$H/deploy/cifar10_accel.hwh"
echo ----IP----
find "$H/notebooks/hls4ml_prj/myproject_prj/solution1/impl/ip" -name 'component.xml' | head
python3 - <<'PY'
from pathlib import Path
root = (Path(__import__("os").environ["EDGEAI_ROOT"]) / 'notebooks/hls4ml_prj/myproject_prj/solution1/impl/ip')
xmls = list(root.rglob("component.xml"))
print("xmls", len(xmls))
for p in xmls[:3]:
    text = p.read_text(errors="replace")
    print("FILE", p)
    for key in ("TDATA_NUM_BYTES", "output_stream", "input_stream"):
        if key in text:
            print(" has", key)
    # print bus interface widths
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if "TDATA_NUM_BYTES" in line or "physical_name" in line and "stream" in line.lower():
            print(line.strip()[:200])
PY
