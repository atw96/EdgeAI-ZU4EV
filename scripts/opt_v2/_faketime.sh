#!/bin/bash
which faketime || echo no_faketime
dpkg -l faketime 2>/dev/null | tail -1 || true
# confirm the overflow: 2610171658 > 2^31-1
python3 - <<'PY'
print(2610171658 > 2**31-1, 2**31-1)
print(2010171200 < 2**31-1)
PY
