#!/usr/bin/env python3
"""Build deploy/cifar10_bench.npz payloads for on-board FPGA benchmark."""
import os
import numpy as np

REPO = os.environ.get(
    "REPO",
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..")),
)
N_SAMPLES = int(os.environ.get("N_SAMPLES", "100"))
OUT_NPZ = os.environ.get("OUT_NPZ", os.path.join(REPO, "deploy", "cifar10_bench.npz"))


def preprocess_to_bytes(img_hwc_uint8):
    float_img = img_hwc_uint8.astype(np.float32) / 255.0
    fixed = np.round(float_img * 1024.0).astype(np.int16)
    fixed = np.clip(fixed, -32768, 32767)
    return fixed.flatten().tobytes()


def main():
    import tensorflow as tf

    (_, _), (x_test, y_test) = tf.keras.datasets.cifar10.load_data()
    n = min(N_SAMPLES, len(x_test))
    payloads = []
    labels = []
    for i in range(n):
        payloads.append(preprocess_to_bytes(x_test[i]))
        labels.append(int(y_test[i]))

    os.makedirs(os.path.dirname(OUT_NPZ), exist_ok=True)
    np.savez(
        OUT_NPZ,
        payloads=np.array(payloads, dtype=object),
        labels=np.array(labels, dtype=np.int32),
    )
    print("Wrote %s (%d samples, %d bytes each)" % (OUT_NPZ, n, len(payloads[0])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
