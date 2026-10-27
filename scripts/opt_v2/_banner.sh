#!/bin/bash
python3 - <<'PY'
import socket
s = socket.socket(); s.settimeout(3)
s.connect((__import__("os").environ["BOARD_IP"], 22))
print(s.recv(200))
s.close()
PY
