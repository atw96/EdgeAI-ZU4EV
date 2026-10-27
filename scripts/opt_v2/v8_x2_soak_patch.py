#!/usr/bin/env python3
from pathlib import Path

p = Path("/tmp/v8_x2_hot.c")
text = p.read_text()
old = """    if (soak) {
        soak_s = atof(argv[2]);
        n = 10000000;
        cap = 2000;
    } else {
        n = atoi(argv[2]);
        cap = n;
    }
    payloads = load_file(argv[3], (size_t)n * IN_BYTES);
    golden = load_file(argv[4], (size_t)n * OUT_DIM * sizeof(int32_t));
    top1 = load_file(argv[5], (size_t)n * sizeof(int32_t));
"""
new = """    int span;
    if (soak) {
        soak_s = atof(argv[2]);
        span = 10000;
        n = 20000000;
        cap = 2000;
    } else {
        n = atoi(argv[2]);
        span = n;
        cap = n;
    }
    payloads = load_file(argv[3], (size_t)span * IN_BYTES);
    golden = load_file(argv[4], (size_t)span * OUT_DIM * sizeof(int32_t));
    top1 = load_file(argv[5], (size_t)span * sizeof(int32_t));
"""
if old not in text:
    raise SystemExit("anchor missing")
text = text.replace(old, new, 1)
text = text.replace(
    "        memcpy(src_map, payloads + (size_t)i * IN_BYTES, IN_BYTES);",
    "        int idx = i % span;\n        memcpy(src_map, payloads + (size_t)idx * IN_BYTES, IN_BYTES);",
    1,
)
text = text.replace("golden[i * OUT_DIM + k]", "golden[idx * OUT_DIM + k]")
text = text.replace("pred != top1[i]", "pred != top1[idx]")
text = text.replace("pred, top1[i]);", "pred, top1[idx]);")
text = text.replace("if (seen % 2000 == 0)", "if (seen % 20000 == 0)")
p.write_text(text)
print("patched", p)
