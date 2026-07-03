#!/usr/bin/env python3
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from v19_hls_config_common import load_gap_model, build_hls_config, configure_rounding_saturation

gap = load_gap_model()
configure_rounding_saturation(gap)
for be in (False, True):
    cfg = build_hls_config(gap, bit_exact=be)
    keys = ['input_qact', 'relu_conv1a', 'relu_conv3b', 'gap']
    out = {k: cfg.get('LayerName', {}).get(k, {}) for k in keys}
    print('bit_exact', be, json.dumps(out, indent=2))
