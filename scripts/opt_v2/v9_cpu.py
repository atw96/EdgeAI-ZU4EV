#!/usr/bin/env python3
"""A53 TFLite INT8 on the same 10k payloads the FPGA cells used.

Two scopes, both reported:
  invoke_ms  — Interpreter.invoke only
  e2e_ms     — payload bytes to class (int16/1024, quantize, invoke, dequant, argmax)

The npz stores 6144-byte Q6 payloads, not a separate uint8 image.
"""
import os
import sys
import time
import zipfile

import numpy as np

WHEEL = "/tmp/edgeai_bench/tflite_runtime.whl"
SITE = "/tmp/edgeai_bench/pylib"
MODEL = "/tmp/edgeai_bench/model_int8.tflite"
NPZ = "/tmp/edgeai_bench/bench10k_packed.npz"


def install():
    os.makedirs(SITE, exist_ok=True)
    if os.path.isdir(os.path.join(SITE, "tflite_runtime")):
        return
    with zipfile.ZipFile(WHEEL) as z:
        names = z.namelist()
        if any(n.startswith("tflite_runtime/") for n in names):
            z.extractall(SITE)
            return
        for name in names:
            if name.endswith("/") or ".data/purelib/" not in name:
                continue
            rel = name.split(".data/purelib/", 1)[1]
            target = os.path.join(SITE, rel)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with z.open(name) as src, open(target, "wb") as dst:
                dst.write(src.read())


def quantize(img, detail):
    dtype = detail["dtype"]
    if dtype == np.int8:
        scale, zp = detail["quantization"]
        return (img / scale + zp).astype(np.int8)
    if dtype == np.uint8:
        return np.rint(img * 255.0).clip(0, 255).astype(np.uint8)
    return img.astype(np.float32)


def dequant_argmax(raw, detail):
    if detail["dtype"] == np.int8:
        scale, zp = detail["quantization"]
        values = (raw.astype(np.float32) - zp) * scale
    elif detail["dtype"] == np.uint8:
        scale, zp = detail["quantization"]
        values = (raw.astype(np.float32) - zp) * scale
    else:
        values = raw.astype(np.float32)
    return int(np.argmax(values))


def median(xs):
    ys = sorted(xs)
    n = len(ys)
    return ys[n // 2]


def one_pass(interpreter, payloads, labels, in_d, out_d):
    invoke_ms = []
    e2e_ms = []
    correct = 0
    for i in range(len(labels)):
        fixed = np.frombuffer(payloads[i].tobytes(), dtype=np.int16).reshape(32, 32, 3)
        img = (fixed.astype(np.float32) / 1024.0).clip(0.0, 1.0)
        inp = quantize(img, in_d)
        t0 = time.perf_counter()
        interpreter.set_tensor(in_d["index"], inp[np.newaxis, ...])
        t1 = time.perf_counter()
        interpreter.invoke()
        t2 = time.perf_counter()
        raw = interpreter.get_tensor(out_d["index"]).reshape(-1)
        pred = dequant_argmax(raw, out_d)
        t3 = time.perf_counter()
        invoke_ms.append((t2 - t1) * 1000.0)
        e2e_ms.append((t3 - t0) * 1000.0)
        if pred == int(labels[i]):
            correct += 1
        if (i + 1) % 2000 == 0:
            print("cpu_progress", i + 1, flush=True)
    n = len(labels)
    return {
        "n": n,
        "top1": correct / n,
        "invoke_ms": median(invoke_ms),
        "e2e_ms": median(e2e_ms),
    }


def main():
    install()
    sys.path.insert(0, SITE)
    import tflite_runtime.interpreter as tflite

    pack = np.load(NPZ)
    payloads = np.asarray(pack["payloads"])
    labels = np.asarray(pack["labels"])
    print("payloads", payloads.shape, payloads.dtype, "labels", labels.shape, flush=True)
    for threads in (1, 4):
        for rep in (1, 2, 3):
            interpreter = tflite.Interpreter(model_path=MODEL, num_threads=threads)
            interpreter.allocate_tensors()
            in_d = interpreter.get_input_details()[0]
            out_d = interpreter.get_output_details()[0]
            if rep == 1 and threads == 1:
                print("input", in_d["shape"].tolist(), str(in_d["dtype"]), in_d["quantization"], flush=True)
                print("output", out_d["shape"].tolist(), str(out_d["dtype"]), out_d["quantization"], flush=True)
            fixed = np.frombuffer(payloads[0].tobytes(), dtype=np.int16).reshape(32, 32, 3)
            img = (fixed.astype(np.float32) / 1024.0).clip(0.0, 1.0)
            warm = quantize(img, in_d)
            for _ in range(5):
                interpreter.set_tensor(in_d["index"], warm[np.newaxis, ...])
                interpreter.invoke()
            t0 = time.perf_counter()
            stats = one_pass(interpreter, payloads, labels, in_d, out_d)
            elapsed = time.perf_counter() - t0
            print(
                "CPU threads %d rep %d top1 %.4f invoke_ms %.4f e2e_ms %.4f elapsed_s %.1f"
                % (threads, rep, stats["top1"], stats["invoke_ms"], stats["e2e_ms"], elapsed),
                flush=True,
            )
    print("CPU_DONE", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
