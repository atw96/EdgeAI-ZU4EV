import numpy as np
from pathlib import Path
d = np.load(Path(__file__).resolve().parents[1] / 'deploy' / 'cifar10_bench.npz', allow_pickle=True)
x = np.frombuffer(bytes(d['payloads'][0]), dtype=np.int16)
print('min', x.min(), 'max', x.max(), 'neg_pct', (x < 0).mean() * 100)
