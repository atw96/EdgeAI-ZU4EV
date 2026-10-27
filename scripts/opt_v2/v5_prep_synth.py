#!/usr/bin/env python3
"""Build the 729-image suite, packed DMA payloads, csim text, and Keras GAP.

Keras sees the same int16/1024 values the board and csim see.
"""
import json
import os
import runpy
from pathlib import Path

import numpy as np

os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "results" / "opt_v2" / "v5_synth"
OUT.mkdir(parents=True, exist_ok=True)
os.chdir(OUT)
runpy.run_path(str(REPO / "docs" / "make_synth_suite.py") if (REPO / "docs" / "make_synth_suite.py").is_file()
               else str(Path(__file__).resolve().parents[2] / 'docs/make_synth_suite.py'))

suite = np.load(OUT / "synth_suite.npz", allow_pickle=True)
images = suite["images"]
names = suite["names"]
cats = suite["cats"]
n = len(images)
payloads = np.empty((n, 6144), dtype=np.uint8)
floats = np.empty((n, 32, 32, 3), dtype=np.float32)
for i in range(n):
    fixed = np.round(images[i].astype(np.float32) / 255.0 * 1024.0).astype(np.int16)
    payloads[i] = np.frombuffer(fixed.tobytes(), dtype=np.uint8)
    floats[i] = fixed.astype(np.float32) / 1024.0
np.savez(OUT / "synth_packed.npz", payloads=payloads, labels=np.zeros(n, np.int32),
         names=names, cats=cats)
lines = []
for i in range(n):
    flat = floats[i].reshape(-1)
    lines.append(" ".join(str(float(v)) for v in flat))
text = "\n".join(lines) + "\n"
(OUT / "tb_input_features.dat").write_text(text)
(OUT / "tb_output_predictions.dat").write_text(text)
print("packed", n, "dat_bytes", (OUT / "tb_input_features.dat").stat().st_size)

from tensorflow import keras
from qkeras import QActivation, QConv2D, QDense, quantized_bits, quantized_relu
custom = {
    "QConv2D": QConv2D, "QDense": QDense, "QActivation": QActivation,
    "quantized_bits": quantized_bits, "quantized_relu": quantized_relu,
}
model = keras.models.load_model(str(REPO / "notebooks" / "model_int8_qkeras.h5"),
                                custom_objects=custom, compile=False)
gap = keras.Model(model.input, model.get_layer("gap").output).predict(floats, verbose=0, batch_size=64)
np.save(OUT / "keras_gap.npy", np.asarray(gap, dtype=np.float32).reshape(n, -1)[:, :24])
print("keras gap", gap.shape)
