from __future__ import annotations

import argparse
import os
import sys

import paramiko


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command")
    parser.add_argument("--host", default="114.111.22.106")
    parser.add_argument("--port", type=int, default=10023)
    parser.add_argument("--user", default="chenwenjin")
    args = parser.parse_args()
    password = os.environ.get("WEEKLY_SERVER_PASSWORD")
    if not password:
        raise SystemExit("WEEKLY_SERVER_PASSWORD is required")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        args.host,
        port=args.port,
        username=args.user,
        password=password,
        timeout=20,
    )
    try:
        _, stdout, stderr = client.exec_command(args.command, timeout=300)
        output = stdout.read()
        error = stderr.read()
        if output:
            sys.stdout.buffer.write(output)
        if error:
            sys.stderr.buffer.write(error)
        return stdout.channel.recv_exit_status()
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
