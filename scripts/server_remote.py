from __future__ import annotations

import argparse
import os
import sys

import paramiko


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", nargs="?")
    parser.add_argument(
        "--upload",
        nargs=2,
        metavar=("LOCAL_PATH", "REMOTE_PATH"),
    )
    parser.add_argument(
        "--configure-api-key",
        action="store_true",
        help="Write WEEKLY_LLM_API_KEY to the server runtime file via SFTP.",
    )
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
        if args.configure_api_key:
            api_key = os.environ.get("WEEKLY_LLM_API_KEY")
            if not api_key:
                raise SystemExit("WEEKLY_LLM_API_KEY is required")
            runtime = (
                f"WEEKLY_LLM_API_KEY={api_key}\n"
                "WEEKLY_LLM_BASE_URL=https://api.openai.com/v1\n"
                "WEEKLY_LLM_MODEL=gpt-5.6\n"
                "WEEKLY_FETCH_FULLTEXT=1\n"
            )
            sftp = client.open_sftp()
            remote_path = (
                "/data1/chenwenjin/services/weekly-report/runtime.env"
            )
            try:
                with sftp.file(remote_path, "w") as handle:
                    handle.write(runtime)
                sftp.chmod(remote_path, 0o600)
            finally:
                sftp.close()
            return 0
        if args.upload:
            local_path, remote_path = args.upload
            sftp = client.open_sftp()
            try:
                sftp.put(local_path, remote_path)
            finally:
                sftp.close()
            return 0
        if not args.command:
            raise SystemExit("command or --upload is required")
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
