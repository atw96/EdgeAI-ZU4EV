#!/usr/bin/env python3
"""Document drift between the fresh P4 export and the pre-A1' project. Read only."""
import filecmp
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
fresh = REPO / 'results' / 'opt_v2' / 'p1_p4_firmware' / 'weights'
old = REPO / 'notebooks' / 'hls4ml_prj.bak_bitexact_opt_v2_A1prime_20261017_092201' / 'firmware' / 'weights'
out = REPO / 'results' / 'opt_v2' / 'p1_drift_vs_deployed_export.json'
if out.exists():
    raise SystemExit('refuse overwrite %s' % out)
differ = []
missing = []
if not old.is_dir():
    raise SystemExit('missing %s' % old)
for path in sorted(fresh.iterdir()):
    other = old / path.name
    if not other.is_file():
        missing.append(path.name)
    elif not filecmp.cmp(path, other, shallow=False):
        differ.append(path.name)
doc = {
    'fresh_p4': str(fresh),
    'previous_export': str(old),
    'n_fresh': len(list(fresh.iterdir())),
    'files_differ': differ,
    'missing_in_previous': missing,
    'note': 'Fresh P4 and fresh A1prime weights match each other. Differences here are export drift versus the project that existed before the v2 A1 convert, not an RF effect.',
}
out.write_text(json.dumps(doc, indent=2), encoding='utf-8')
print(json.dumps({'n_differ': len(differ), 'names': differ[:20]}, indent=2))
