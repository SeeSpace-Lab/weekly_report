from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from .db import Database
from .review import ReviewService


class ReviewAPI:
    def __init__(
        self,
        database: Database,
        approve_command: tuple[str, ...],
        allowed_origin: str,
    ):
        self.database = database
        self.approve_command = approve_command
        self.allowed_origin = allowed_origin.rstrip("/")
        self._lock = threading.Lock()

    def status(self, department_id: str = "orbitinfer") -> dict[str, Any]:
        service = ReviewService(self.database)
        readiness = service.approval_readiness(
            service.current_issue_id(department_id)
        )
        return {
            "departmentId": department_id,
            "issueId": readiness.issue_id,
            "isoWeek": readiness.iso_week,
            "status": readiness.status,
            "ready": readiness.ready,
            "blockers": list(readiness.blockers),
        }

    def approve(self, department_id: str = "orbitinfer") -> dict[str, Any]:
        if not self._lock.acquire(blocking=False):
            raise RuntimeError("另一项审核同步任务正在执行")
        try:
            readiness = self.status(department_id)
            if not readiness["ready"]:
                raise ValueError("; ".join(readiness["blockers"]))
            result = subprocess.run(
                [
                    *self.approve_command,
                    "--department",
                    department_id,
                ],
                cwd=Path(__file__).resolve().parents[2],
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=300,
                check=False,
            )
            if result.returncode:
                detail = (result.stderr or result.stdout).strip()[-2000:]
                raise RuntimeError(f"审核同步失败：{detail}")
            payload = self.status(department_id)
            payload["synced"] = True
            return payload
        finally:
            self._lock.release()


def make_handler(api: ReviewAPI) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "weekly-review-api/1"

        def _json(
            self, status: HTTPStatus, payload: dict[str, Any]
        ) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            origin = self.headers.get("Origin")
            if origin and origin.rstrip("/") == api.allowed_origin:
                self.send_header(
                    "Access-Control-Allow-Origin",
                    api.allowed_origin,
                )
            self.end_headers()
            self.wfile.write(body)

        def _origin_allowed(self) -> bool:
            origin = self.headers.get("Origin")
            if not origin:
                return True
            return origin.rstrip("/") == api.allowed_origin

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path != "/api/review/status":
                self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})
                return
            department_id = parse_qs(parsed.query).get(
                "department",
                ["orbitinfer"],
            )[0]
            try:
                self._json(HTTPStatus.OK, api.status(department_id))
            except Exception as error:
                self._json(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    {"error": str(error)},
                )

        def do_POST(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path != "/api/review/approve":
                self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})
                return
            department_id = parse_qs(parsed.query).get(
                "department",
                ["orbitinfer"],
            )[0]
            if not self._origin_allowed():
                self._json(HTTPStatus.FORBIDDEN, {"error": "invalid origin"})
                return
            if self.headers.get("Content-Length", "0") not in {"", "0"}:
                self._json(
                    HTTPStatus.BAD_REQUEST,
                    {"error": "request body is not accepted"},
                )
                return
            try:
                self._json(
                    HTTPStatus.OK,
                    api.approve(department_id),
                )
            except ValueError as error:
                self._json(HTTPStatus.CONFLICT, {"error": str(error)})
            except Exception as error:
                self._json(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    {"error": str(error)},
                )

        def log_message(self, format: str, *args: object) -> None:
            print(
                f"{self.address_string()} - {format % args}",
                flush=True,
            )

    return Handler


def main() -> None:
    root = Path(
        os.environ.get(
            "WEEKLY_ROOT",
            Path(__file__).resolve().parents[2],
        )
    )
    database = Database(root / "data" / "weekly_intel.db")
    database.initialize(root / "schemas" / "weekly_intel.sql")
    configured_command = os.environ.get("WEEKLY_APPROVE_COMMAND")
    if configured_command:
        approve_command = (configured_command,)
    else:
        approve_command = (
            sys.executable,
            str((root / "scripts" / "approve_and_sync.py").resolve()),
        )
    api = ReviewAPI(
        database=database,
        approve_command=approve_command,
        allowed_origin=os.environ.get(
            "WEEKLY_REVIEW_ORIGIN",
            "http://127.0.0.1:3000",
        ),
    )
    server = ThreadingHTTPServer(
        (
            os.environ.get("WEEKLY_REVIEW_API_HOST", "127.0.0.1"),
            int(os.environ.get("WEEKLY_REVIEW_API_PORT", "8010")),
        ),
        make_handler(api),
    )
    server.serve_forever()


if __name__ == "__main__":
    main()
