#!/usr/bin/env python3
"""Quick probe: QActivation API variants for Route 1 P2."""
import inspect
from qkeras import QActivation, quantized_bits, quantized_relu

print('QActivation sig:', inspect.signature(QActivation.__init__))
for label, act in [
    ('relu6', quantized_relu(6)),
    ('bits6', quantized_bits(6, 0, alpha='auto_po2')),
]:
    try:
        layer = QActivation(act, name='probe')
        print(label, 'OK', layer.__class__.__name__)
    except Exception as e:
        print(label, 'FAIL', e)

try:
    layer = QActivation(
        quantized_bits(6, 0, alpha='auto_po2'),
        name='probe2',
        relu_upper_bound=1.0,
    )
    print('bits6+relu_upper_bound OK')
except Exception as e:
    print('bits6+relu_upper_bound FAIL', e)
