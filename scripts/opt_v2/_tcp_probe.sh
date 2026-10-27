#!/bin/bash
echo test22
timeout 2 bash -c 'echo >/dev/tcp/${BOARD_SUBNET:?BOARD_SUBNET}.1/22' && echo gw22_open || echo gw22_closed
timeout 2 bash -c 'echo >/dev/tcp/${BOARD_SUBNET:?BOARD_SUBNET}.1/80' && echo gw80_open || echo gw80_closed
python3 - <<'PY'
import os
import socket
for ip in [os.environ["BOARD_SUBNET"] + ".1", os.environ["BOARD_IP"]]:
    s = socket.socket(); s.settimeout(0.4)
    try:
        s.connect((ip, 22))
        print("OPEN", ip)
    except Exception as e:
        print("NO", ip, type(e).__name__)
    finally:
        s.close()
PY
