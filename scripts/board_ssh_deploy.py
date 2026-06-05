#!/usr/bin/env python3
"""SSH deploy + force PL reload + single DMA verify script."""
import os
import sys
import time
from pathlib import Path

try:
    import paramiko
except ImportError:
    print("pip install paramiko==2.12.0")
    sys.exit(1)

BOARD = os.environ.get("BOARD_IP", "192.168.0.100")
USER = os.environ.get("BOARD_USER", "root")
PASS = os.environ.get("BOARD_PASS", "root")
REPO = Path(os.environ.get("REPO", Path(__file__).resolve().parent.parent))


def ssh_run(client, cmd, timeout=120):
    print("+", cmd)
    _, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    code = stdout.channel.recv_exit_status()
    if out:
        print(out, end="" if out.endswith("\n") else "\n")
    if err:
        print(err, end="" if err.endswith("\n") else "\n", file=sys.stderr)
    return code


def sftp_put(sftp, local, remote):
    print("upload %s -> %s" % (local, remote))
    sftp.put(str(local), remote)


def main():
    try:
        transport_cls = paramiko.Transport
        if hasattr(transport_cls, "_preferred_keys"):
            transport_cls._preferred_keys = ("ssh-rsa", "ssh-ed25519", "ecdsa-sha2-nistp256")
    except Exception:
        pass

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        BOARD,
        username=USER,
        password=PASS,
        allow_agent=False,
        look_for_keys=False,
        timeout=20,
        disabled_algorithms={
            "keys": ["rsa-sha2-512", "rsa-sha2-256"],
            "pubkeys": ["rsa-sha2-512", "rsa-sha2-256"],
        },
    )
    sftp = client.open_sftp()

    bit = REPO / "deploy" / "cifar10_accel.bit"
    if not bit.is_file():
        print("missing", bit)
        return 1

    ssh_run(client, "mkdir -p /lib/firmware /root/firmware /tmp")
    sftp_put(sftp, bit, "/lib/firmware/cifar10_accel.bit")
    sftp_put(sftp, bit, "/root/firmware/cifar10_accel.bit")

    for name in ("board_load_only.sh", "board_dma_verify.py", "board_infer.py"):
        src = REPO / "scripts" / name
        if src.is_file():
            sftp_put(sftp, src, "/tmp/" + name)

    ssh_run(client, "chmod +x /tmp/board_load_only.sh")
    ssh_run(client, "FORCE_PL_RELOAD=1 sh /tmp/board_load_only.sh", timeout=90)
    time.sleep(0.5)
    rc = ssh_run(client, "python3 -u /tmp/board_dma_verify.py", timeout=90)

    if os.environ.get("RUN_INFER") == "1":
        ssh_run(client, "python3 -u /tmp/board_infer.py", timeout=120)

    sftp.close()
    client.close()
    return rc


if __name__ == "__main__":
    sys.exit(main())
