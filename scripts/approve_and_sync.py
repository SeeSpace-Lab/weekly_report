from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ALLOWED_PREFIXES = (
    "outputs/orbitinfer/",
    "site/app/report-data.json",
    "site/app/archive-data.json",
    "site/app/library-data.json",
    "site/app/source-data.json",
)


def run(command: list[str], cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        check=True,
        text=True,
        encoding="utf-8",
    )


def main() -> int:
    status = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=no"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout.splitlines()
    unexpected = []
    for line in status:
        path = line[3:].replace("\\", "/")
        if not any(
            path == prefix or path.startswith(prefix)
            for prefix in ALLOWED_PREFIXES
        ):
            unexpected.append(line)
    if unexpected:
        raise RuntimeError(
            "本地工作区存在周报数据以外的未提交改动，拒绝审核同步：\n"
            + "\n".join(unexpected)
        )

    run(
        [
            sys.executable,
            "-m",
            "weekly_intel.cli",
            "approve-and-export",
            "--reviewer",
            "local-review-site",
            "--output",
            str(ROOT / "site" / "app" / "report-data.json"),
        ]
    )
    npm = "npm.cmd" if sys.platform == "win32" else "npm"
    run([npm, "run", "build"], ROOT / "site")
    run(
        [
            "git",
            "add",
            "site/app/report-data.json",
            "site/app/archive-data.json",
            "site/app/library-data.json",
            "site/app/source-data.json",
            "outputs/orbitinfer",
        ]
    )
    report = json.loads(
        (ROOT / "site" / "app" / "report-data.json").read_text(
            encoding="utf-8"
        )
    )
    iso_week = str(report["issue"]["isoWeek"])
    staged = subprocess.run(
        ["git", "diff", "--cached", "--quiet"], cwd=ROOT, check=False
    )
    if staged.returncode:
        run(["git", "commit", "-m", f"Approve {iso_week} weekly report"])
        run(["git", "push", "origin", "main"])
    print(
        json.dumps(
            {"status": "approved", "isoWeek": iso_week, "synced": True},
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
