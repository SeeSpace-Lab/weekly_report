from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from weekly_intel.config import department_slug, find_department
from weekly_intel.db import Database
from weekly_intel.review import ReviewService


ROOT = Path(__file__).resolve().parents[1]
SHARED_ALLOWED_PREFIXES = (
    "site/app/department-data.json",
    "site/app/library-data.json",
    "site/app/source-data.json",
    "site/app/archive-data.json",
    "site/app/data/departments/",
)


def run(command: list[str], cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        check=True,
        text=True,
        encoding="utf-8",
    )


def current_branch() -> str:
    return run(
        ["git", "branch", "--show-current"],
    ).stdout.strip()


def assert_git_index_writable() -> None:
    git_dir_text = subprocess.run(
        ["git", "rev-parse", "--git-dir"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout.strip()
    git_dir = Path(git_dir_text)
    if not git_dir.is_absolute():
        git_dir = ROOT / git_dir
    lock = git_dir / "index.lock"
    descriptor: int | None = None
    created = False
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        created = True
        os.close(descriptor)
        descriptor = None
        lock.unlink()
        created = False
    except OSError as error:
        if descriptor is not None:
            os.close(descriptor)
        if created and lock.exists():
            lock.unlink(missing_ok=True)
        raise RuntimeError(
            "本地审核服务没有 Git 写权限，尚未改变本期审核状态。"
            "请重新启动本地审核服务后再确认。"
        ) from error


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--department", default="orbitinfer")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    branch = current_branch()
    if branch in {"main", "develop"}:
        raise RuntimeError(
            f"Refusing to approve directly on protected branch {branch}; "
            "use a feature/* or fix/* branch and open a pull request."
        )
    department = find_department(
        ROOT / "config" / "departments",
        args.department,
        sources_path=ROOT / "config" / "sources.yaml",
    )
    department_id = str(department["department_id"])
    slug = department_slug(department)
    allowed_prefixes = (
        f"outputs/{department_id}/",
        *SHARED_ALLOWED_PREFIXES,
    )
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
            for prefix in allowed_prefixes
        ):
            unexpected.append(line)
    if unexpected:
        raise RuntimeError(
            "本地工作区存在当前部门周报数据以外的未提交改动，"
            "拒绝审核同步：\n" + "\n".join(unexpected)
        )

    assert_git_index_writable()
    database = Database(ROOT / "data" / "weekly_intel.db")
    database.initialize(ROOT / "schemas" / "weekly_intel.sql")
    issue_id = ReviewService(database).current_issue_id(department_id)
    report_path = (
        ROOT
        / "site"
        / "app"
        / "data"
        / "departments"
        / slug
        / "report.json"
    )
    reviewer = str(
        department.get("owners", {}).get(
            "reviewer_label",
            f"{department_id}-local-review",
        )
    )
    run(
        [
            sys.executable,
            "-m",
            "weekly_intel.cli",
            "approve-and-export",
            "--issue-id",
            issue_id,
            "--reviewer",
            reviewer,
            "--output",
            str(report_path),
        ]
    )
    npm = "npm.cmd" if sys.platform == "win32" else "npm"
    run([npm, "run", "build"], ROOT / "site")
    run(
        [
            "git",
            "add",
            str(report_path.relative_to(ROOT)),
            "site/app/department-data.json",
            "site/app/library-data.json",
            "site/app/source-data.json",
            "site/app/archive-data.json",
            f"outputs/{department_id}",
        ]
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    iso_week = str(report["issue"]["isoWeek"])
    staged = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        cwd=ROOT,
        check=False,
    )
    if staged.returncode:
        run(
            [
                "git",
                "commit",
                "-m",
                f"feat(report): approve {department_id} {iso_week} weekly report",
            ]
        )
        run(["git", "push", "-u", "origin", branch])
    print(
        json.dumps(
            {
                "status": "approved",
                "departmentId": department_id,
                "isoWeek": iso_week,
                "synced": True,
                "publicationTriggered": False,
                "nextStep": "Open a pull request; production publication occurs after merge to main.",
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
