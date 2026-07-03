#!/usr/bin/env python3
"""Debug QActivation layer activation attribute."""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'scripts'))
from v19_hls_config_common import load_full_model  # noqa: E402

m = load_full_model()
for l in m.layers:
    if 'relu' in l.name or l.name == 'input_qact':
        act = getattr(l, 'activation', None)
        print(l.name, type(l).__name__, 'activation=', act, type(act))
