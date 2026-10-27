#!/usr/bin/env python3
import os
"""Find a dropbear SSH server on BOARD_SUBNET.0/24."""
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed

def probe(ip):
    s = socket.socket()
    s.settimeout(0.35)
    try:
        s.connect((ip, 22))
        data = s.recv(80)
        return ip, data.decode("ascii", "replace").strip()
    except Exception:
        return None
    finally:
        s.close()

ips = [os.environ["BOARD_SUBNET"] + ".%d" % i for i in range(1, 255)]
hits = []
with ThreadPoolExecutor(max_workers=64) as ex:
    futs = [ex.submit(probe, ip) for ip in ips]
    for f in as_completed(futs):
        r = f.result()
        if r:
            hits.append(r)
            print("HIT", r[0], r[1], flush=True)
print("count", len(hits))
