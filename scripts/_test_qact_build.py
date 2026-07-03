#!/usr/bin/env python3
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'scripts'))
from v19_qat_input_qact_finetune import build_q6_input_qact

import tensorflow as tf
from tensorflow.keras import layers
from qkeras import QActivation, QConv2D, QDense, quantized_bits, quantized_relu

m = build_q6_input_qact(tf.keras, layers, QConv2D, QDense, QActivation, quantized_bits, quantized_relu)
print('OK layers:', len(m.layers))
print('qact:', [l.name for l in m.layers if 'qact' in l.name])
