from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .candidates import rank_candidates
from .calendar_window import previous_complete_week
from .config import load_departments, load_sources, load_yaml
from .contracts import CollectionWindow
from .db import Database
from .service import CollectionService
from .review import ReviewService
from .render import MarkdownRenderAgent
from .orchestrator import WeeklyOrchestrator
from .weekly import WeeklyPipelineService
from .site_export import SiteDataExportAgent
from .codex_handoff import CodexWeeklyHandoff


def _default_root() -> Path:
    return Path(__file__).resolve().parents[2]


def build_parser() -> argparse.ArgumentParser:
    root = _default_root()
    parser = argparse.ArgumentParser(prog="weekly-intel")
    parser.add_argument(
        "--db", type=Path, default=root / "data" / "weekly_intel.db"
    )
    parser.add_argument(
        "--schema", type=Path, default=root / "schemas" / "weekly_intel.sql"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init-db")

    validate_departments = subparsers.add_parser("validate-departments")
    validate_departments.add_argument(
        "--directory",
        type=Path,
        default=root / "config" / "departments",
    )
    validate_departments.add_argument(
        "--sources",
        type=Path,
        default=root / "config" / "sources.yaml",
    )

    sync_departments = subparsers.add_parser("sync-departments")
    sync_departments.add_argument(
        "--directory",
        type=Path,
        default=root / "config" / "departments",
    )
    sync_departments.add_argument(
        "--sources",
        type=Path,
        default=root / "config" / "sources.yaml",
    )
    sync_departments.add_argument(
        "--output",
        type=Path,
        default=root / "site" / "app" / "department-data.json",
    )

    arxiv = subparsers.add_parser("collect-arxiv")
    arxiv.add_argument("--days", type=int, default=7)
    arxiv.add_argument("--limit", type=int, default=200)
    arxiv.add_argument(
        "--sources", type=Path, default=root / "config" / "sources.yaml"
    )

    openreview = subparsers.add_parser("collect-openreview")
    openreview.add_argument("--days", type=int, default=7)
    openreview.add_argument("--page-size", type=int, default=500)
    openreview.add_argument("--max-pages", type=int, default=10)
    openreview.add_argument(
        "--sources", type=Path, default=root / "config" / "sources.yaml"
    )

    crossref = subparsers.add_parser("collect-crossref")
    crossref.add_argument("--days", type=int, default=7)
    crossref.add_argument("--rows-per-query", type=int, default=50)
    crossref.add_argument(
        "--sources", type=Path, default=root / "config" / "sources.yaml"
    )

    github = subparsers.add_parser("collect-github")
    github.add_argument("--days", type=int, default=7)
    github.add_argument("--per-page", type=int, default=100)
    github.add_argument("--source-id", action="append")
    github.add_argument(
        "--sources", type=Path, default=root / "config" / "sources.yaml"
    )

    manual = subparsers.add_parser("collect-manual")
    manual.add_argument("--days", type=int, default=30)
    manual.add_argument("--inbox", type=Path)
    manual.add_argument(
        "--sources", type=Path, default=root / "config" / "sources.yaml"
    )

    huggingface = subparsers.add_parser("collect-huggingface")
    huggingface.add_argument("--days", type=int, default=7)
    huggingface.add_argument("--limit-per-query", type=int, default=20)
    huggingface.add_argument(
        "--sources", type=Path, default=root / "config" / "sources.yaml"
    )

    wechat = subparsers.add_parser("collect-wechat")
    wechat.add_argument("--days", type=int, default=7)
    wechat.add_argument("--source-id", action="append")
    wechat.add_argument(
        "--sources", type=Path, default=root / "config" / "sources.yaml"
    )

    venues = subparsers.add_parser("collect-venues")
    venues.add_argument("--days", type=int, default=7)
    venues.add_argument(
        "--sources", type=Path, default=root / "config" / "sources.yaml"
    )

    candidates = subparsers.add_parser("list-candidates")
    candidates.add_argument("--limit", type=int, default=30)
    candidates.add_argument(
        "--department",
        type=Path,
        default=root / "config" / "departments" / "orbitinfer.yaml",
    )

    weekly = subparsers.add_parser("build-weekly")
    weekly.add_argument("--days", type=int, default=7)
    weekly.add_argument("--iso-week")
    weekly.add_argument("--output", type=Path)
    weekly.add_argument(
        "--site-data",
        type=Path,
        help="Export the built issue for the web front end.",
    )
    weekly.add_argument(
        "--department",
        type=Path,
        default=root / "config" / "departments" / "orbitinfer.yaml",
    )

    queue = subparsers.add_parser("review-queue")
    queue.add_argument("--issue-id")

    review = subparsers.add_parser("review-selection")
    review.add_argument("selection_id")
    review.add_argument(
        "--decision",
        required=True,
        choices=["approve", "reject", "revise", "defer"],
    )
    review.add_argument("--reviewer", required=True)
    review.add_argument("--comment")

    approve = subparsers.add_parser("approve-issue")
    approve.add_argument("issue_id")

    approve_export = subparsers.add_parser("approve-and-export")
    approve_export.add_argument("--issue-id")
    approve_export.add_argument("--reviewer", default="private-review-site")
    approve_export.add_argument(
        "--output",
        type=Path,
        default=root / "site" / "app" / "report-data.json",
    )

    publish = subparsers.add_parser("publish-issue")
    publish.add_argument("issue_id")
    publish.add_argument("--page-url")

    run_weekly = subparsers.add_parser("run-weekly")
    run_weekly.add_argument("--days", type=int, default=7)
    run_weekly.add_argument(
        "--window-mode",
        choices=["closed-week", "rolling"],
        default="closed-week",
        help=(
            "closed-week builds the previous local Monday-Sunday period; "
            "rolling preserves the legacy trailing-N-days behavior"
        ),
    )
    run_weekly.add_argument("--iso-week")
    run_weekly.add_argument(
        "--skip-wechat",
        action="store_true",
        help="Build the issue without collecting configured WeChat sources.",
    )
    run_weekly.add_argument("--output", type=Path)
    run_weekly.add_argument(
        "--sources", type=Path, default=root / "config" / "sources.yaml"
    )
    run_weekly.add_argument(
        "--department",
        type=Path,
        default=root / "config" / "departments" / "orbitinfer.yaml",
    )
    run_weekly.add_argument(
        "--audit-directory", type=Path, default=root / "runs"
    )
    run_weekly.add_argument(
        "--site-data",
        type=Path,
        default=root / "site" / "app" / "report-data.json",
        help="Export the built issue for the web front end; pass an empty path only via API to disable.",
    )

    export_site = subparsers.add_parser("export-site-data")
    export_site.add_argument("issue_id")
    export_site.add_argument(
        "--output",
        type=Path,
        default=root / "site" / "app" / "report-data.json",
    )

    codex_brief = subparsers.add_parser("export-codex-brief")
    codex_brief.add_argument("--issue-id")
    codex_brief.add_argument("--limit", type=int, default=30)
    codex_brief.add_argument(
        "--department",
        type=Path,
        default=root / "config" / "departments" / "orbitinfer.yaml",
    )
    codex_brief.add_argument(
        "--output",
        type=Path,
        default=root / "runs" / "codex" / "current-brief.json",
    )

    codex_import = subparsers.add_parser("import-codex-analysis")
    codex_import.add_argument("payload", type=Path)
    codex_import.add_argument(
        "--department",
        type=Path,
        default=root / "config" / "departments" / "orbitinfer.yaml",
    )
    codex_import.add_argument("--output", type=Path)
    codex_import.add_argument(
        "--site-data",
        type=Path,
        default=root / "site" / "app" / "report-data.json",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    database = Database(args.db)
    if args.command == "init-db":
        database.initialize(args.schema)
        print(json.dumps({"status": "ok", "database": str(args.db)}))
        return 0
    if args.command == "validate-departments":
        departments = load_departments(
            args.directory,
            sources_path=args.sources,
        )
        print(
            json.dumps(
                {
                    "status": "ok",
                    "departments": [
                        {
                            "department_id": department["department_id"],
                            "enabled": department.get("enabled", True),
                        }
                        for department in departments
                    ],
                },
                ensure_ascii=False,
            )
        )
        return 0
    if args.command == "sync-departments":
        load_departments(args.directory, sources_path=args.sources)
        database.initialize(args.schema)
        with database.session() as connection:
            output = SiteDataExportAgent().export_departments(
                connection,
                args.directory,
                args.output,
            )
        print(
            json.dumps(
                {"status": "ok", "output": str(output)},
                ensure_ascii=False,
            )
        )
        return 0
    if args.command == "collect-arxiv":
        database.initialize(args.schema)
        sources = load_sources(args.sources)
        source = sources["arxiv"]
        end = datetime.now(timezone.utc)
        window = CollectionWindow(end - timedelta(days=args.days), end)
        batch = CollectionService(database).collect_arxiv(
            source, window, args.limit
        )
        print(
            json.dumps(
                {
                    "run_id": batch.run_id,
                    "status": batch.status.value,
                    "documents": len(batch.documents),
                    "cursor": batch.next_cursor,
                    "errors": [asdict(error) for error in batch.errors],
                    "stats": batch.stats,
                },
                ensure_ascii=False,
            )
        )
        return 0 if batch.status.value in {"ok", "unchanged", "partial"} else 1
    if args.command == "collect-openreview":
        database.initialize(args.schema)
        sources = load_sources(args.sources)
        source = sources["openreview"]
        end = datetime.now(timezone.utc)
        window = CollectionWindow(end - timedelta(days=args.days), end)
        batch = CollectionService(database).collect_openreview(
            source, window, args.page_size, args.max_pages
        )
        print(
            json.dumps(
                {
                    "run_id": batch.run_id,
                    "status": batch.status.value,
                    "documents": len(batch.documents),
                    "cursor": batch.next_cursor,
                    "errors": [asdict(error) for error in batch.errors],
                    "stats": batch.stats,
                },
                ensure_ascii=False,
            )
        )
        return 0 if batch.status.value in {"ok", "unchanged", "partial"} else 1
    if args.command == "collect-crossref":
        database.initialize(args.schema)
        sources = load_sources(args.sources)
        end = datetime.now(timezone.utc)
        window = CollectionWindow(end - timedelta(days=args.days), end)
        batch = CollectionService(database).collect_crossref(
            sources["crossref"], window, args.rows_per_query
        )
        print(
            json.dumps(
                {
                    "run_id": batch.run_id,
                    "status": batch.status.value,
                    "documents": len(batch.documents),
                    "errors": [asdict(error) for error in batch.errors],
                    "stats": batch.stats,
                },
                ensure_ascii=False,
            )
        )
        return 0 if batch.status.value in {"ok", "unchanged", "partial"} else 1
    if args.command == "collect-github":
        database.initialize(args.schema)
        sources = load_sources(args.sources)
        selected_ids = args.source_id or [
            source_id
            for source_id, source in sources.items()
            if source.connector == "GitHubCollector" and source.enabled
        ]
        end = datetime.now(timezone.utc)
        window = CollectionWindow(end - timedelta(days=args.days), end)
        service = CollectionService(database)
        batches = [
            service.collect_github(sources[source_id], window, args.per_page)
            for source_id in selected_ids
        ]
        print(
            json.dumps(
                [
                    {
                        "source_id": batch.source_id,
                        "run_id": batch.run_id,
                        "status": batch.status.value,
                        "documents": len(batch.documents),
                        "errors": [asdict(error) for error in batch.errors],
                        "stats": batch.stats,
                    }
                    for batch in batches
                ],
                ensure_ascii=False,
            )
        )
        return (
            0
            if all(
                batch.status.value in {"ok", "unchanged", "partial"}
                for batch in batches
            )
            else 1
        )
    if args.command == "collect-manual":
        database.initialize(args.schema)
        sources = load_sources(args.sources)
        end = datetime.now(timezone.utc)
        window = CollectionWindow(end - timedelta(days=args.days), end)
        batch = CollectionService(database).collect_manual(
            sources["manual_inbox"], window, args.inbox
        )
        print(
            json.dumps(
                {
                    "run_id": batch.run_id,
                    "status": batch.status.value,
                    "documents": len(batch.documents),
                    "errors": [asdict(error) for error in batch.errors],
                    "stats": batch.stats,
                },
                ensure_ascii=False,
            )
        )
        return 0 if batch.status.value in {"ok", "unchanged", "partial"} else 1
    if args.command == "collect-huggingface":
        database.initialize(args.schema)
        sources = load_sources(args.sources)
        end = datetime.now(timezone.utc)
        window = CollectionWindow(end - timedelta(days=args.days), end)
        batch = CollectionService(database).collect_huggingface(
            sources["huggingface_hub"], window, args.limit_per_query
        )
        print(
            json.dumps(
                {
                    "run_id": batch.run_id,
                    "status": batch.status.value,
                    "documents": len(batch.documents),
                    "errors": [asdict(error) for error in batch.errors],
                    "stats": batch.stats,
                },
                ensure_ascii=False,
            )
        )
        return 0 if batch.status.value in {"ok", "unchanged", "partial"} else 1
    if args.command == "collect-wechat":
        database.initialize(args.schema)
        sources = load_sources(args.sources)
        selected_ids = args.source_id or [
            source_id
            for source_id, source in sources.items()
            if source.connector == "WechatPoolCollector" and source.enabled
        ]
        end = datetime.now(timezone.utc)
        window = CollectionWindow(end - timedelta(days=args.days), end)
        service = CollectionService(database)
        batches = [
            service.collect_wechat(sources[source_id], window)
            for source_id in selected_ids
        ]
        print(
            json.dumps(
                [
                    {
                        "source_id": batch.source_id,
                        "run_id": batch.run_id,
                        "status": batch.status.value,
                        "documents": len(batch.documents),
                        "errors": [asdict(error) for error in batch.errors],
                        "stats": batch.stats,
                    }
                    for batch in batches
                ],
                ensure_ascii=False,
            )
        )
        return (
            0
            if all(
                batch.status.value in {"ok", "unchanged", "partial"}
                for batch in batches
            )
            else 1
        )
    if args.command == "collect-venues":
        database.initialize(args.schema)
        sources = load_sources(args.sources)
        end = datetime.now(timezone.utc)
        window = CollectionWindow(end - timedelta(days=args.days), end)
        batch = CollectionService(database).collect_venues(
            sources["venue_official_pages"], window
        )
        print(
            json.dumps(
                {
                    "run_id": batch.run_id,
                    "status": batch.status.value,
                    "documents": len(batch.documents),
                    "errors": [asdict(error) for error in batch.errors],
                    "stats": batch.stats,
                },
                ensure_ascii=False,
            )
        )
        return 0 if batch.status.value in {"ok", "unchanged", "partial"} else 1
    if args.command == "list-candidates":
        database.initialize(args.schema)
        department = load_yaml(args.department)
        with database.session() as connection:
            candidates = rank_candidates(connection, department, args.limit)
        print(json.dumps(candidates, ensure_ascii=False, indent=2))
        return 0
    if args.command == "build-weekly":
        database.initialize(args.schema)
        department = load_yaml(args.department)
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=args.days)
        iso_year, iso_number, _ = end.isocalendar()
        iso_week = args.iso_week or f"{iso_year}-W{iso_number:02d}"
        output = args.output or (
            _default_root()
            / "outputs"
            / department["department_id"]
            / f"{iso_week}.md"
        )
        result = WeeklyPipelineService(database, department).build(
            iso_week, start, end, output
        )
        exported_site_data = None
        if args.site_data is not None:
            with database.transaction() as connection:
                exported_site_data = SiteDataExportAgent().export(
                    connection, result.issue_id, args.site_data
                )
        print(
            json.dumps(
                {
                    "issue_id": result.issue_id,
                    "assessed": result.assessed_count,
                    "trends": result.trend_count,
                    "selections": result.selection_count,
                    "estimated_read_minutes": result.estimated_read_minutes,
                    "version_diffs": result.version_diffs,
                    "interpretation_claims": result.interpretation_claims,
                    "interpretation_links": result.interpretation_links,
                    "deep_reads": result.deep_reads,
                    "paper_contents_fetched": result.paper_contents_fetched,
                    "paper_contents_failed": result.paper_contents_failed,
                    "output": str(result.output_path),
                    "site_data": (
                        str(exported_site_data)
                        if exported_site_data is not None
                        else None
                    ),
                },
                ensure_ascii=False,
            )
        )
        return 0
    if args.command == "review-queue":
        database.initialize(args.schema)
        with database.session() as connection:
            rows = connection.execute(
                """
                SELECT s.selection_id, s.issue_id, i.iso_week,
                       r.canonical_title, s.section, s.selection_reason,
                       s.requires_human_review
                FROM weekly_selections s
                JOIN weekly_issues i ON i.issue_id=s.issue_id
                JOIN research_items r ON r.item_id=s.item_id
                WHERE (? IS NULL OR s.issue_id=?)
                  AND i.status IN ('draft', 'review')
                ORDER BY i.iso_week DESC, s.section, s.position
                """,
                (args.issue_id, args.issue_id),
            ).fetchall()
        print(
            json.dumps([dict(row) for row in rows], ensure_ascii=False, indent=2)
        )
        return 0
    if args.command == "review-selection":
        database.initialize(args.schema)
        review_id = ReviewService(database).review_selection(
            args.selection_id, args.reviewer, args.decision, args.comment
        )
        print(json.dumps({"review_id": review_id, "status": "ok"}))
        return 0
    if args.command == "approve-issue":
        database.initialize(args.schema)
        ReviewService(database).approve_issue(args.issue_id)
        print(json.dumps({"issue_id": args.issue_id, "status": "approved"}))
        return 0
    if args.command == "approve-and-export":
        database.initialize(args.schema)
        service = ReviewService(database)
        issue_id = args.issue_id or service.current_issue_id()
        readiness = service.approve_all_and_export(
            issue_id, args.reviewer, args.output
        )
        print(
            json.dumps(
                {
                    "issue_id": issue_id,
                    "iso_week": readiness.iso_week,
                    "status": readiness.status,
                    "ready": readiness.ready,
                    "blockers": readiness.blockers,
                    "output": str(args.output.resolve()),
                },
                ensure_ascii=False,
            )
        )
        return 0
    if args.command == "publish-issue":
        database.initialize(args.schema)
        ReviewService(database).publish_issue(args.issue_id, args.page_url)
        print(json.dumps({"issue_id": args.issue_id, "status": "published"}))
        return 0
    if args.command == "run-weekly":
        database.initialize(args.schema)
        department = load_yaml(args.department)
        now = datetime.now(timezone.utc)
        if args.window_mode == "closed-week":
            calendar_window = previous_complete_week(
                now,
                str(department.get("timezone", "Asia/Shanghai")),
            )
            start = calendar_window.start
            end = calendar_window.end
            iso_week = args.iso_week or calendar_window.iso_week
        else:
            end = now
            start = end - timedelta(days=args.days)
            year, week, _ = end.isocalendar()
            iso_week = args.iso_week or f"{year}-W{week:02d}"
        output = args.output or (
            _default_root()
            / "outputs"
            / department["department_id"]
            / f"{iso_week}.md"
        )
        with database.session() as connection:
            protected_issue = connection.execute(
                """
                SELECT issue_id, status, window_start, window_end
                FROM weekly_issues
                WHERE department_id = ? AND iso_week = ?
                  AND status IN ('approved', 'published')
                """,
                (department["department_id"], iso_week),
            ).fetchone()
        if protected_issue:
            metadata_updated = False
            if (
                args.window_mode == "closed-week"
                and (
                    protected_issue["window_start"] != start.isoformat()
                    or protected_issue["window_end"] != end.isoformat()
                )
            ):
                with database.transaction() as connection:
                    connection.execute(
                        """
                        UPDATE weekly_issues
                        SET window_start=?, window_end=?
                        WHERE issue_id=?
                        """,
                        (
                            start.isoformat(),
                            end.isoformat(),
                            protected_issue["issue_id"],
                        ),
                    )
                    MarkdownRenderAgent().write(
                        connection,
                        protected_issue["issue_id"],
                        output,
                    )
                    if args.site_data is not None:
                        SiteDataExportAgent().export(
                            connection,
                            protected_issue["issue_id"],
                            args.site_data,
                        )
                metadata_updated = True
            print(
                json.dumps(
                    {
                        "status": "skipped_protected",
                        "reason": (
                            f"{iso_week} is already "
                            f"{protected_issue['status']}"
                        ),
                        "issue_id": protected_issue["issue_id"],
                        "iso_week": iso_week,
                        "window_start": start.isoformat(),
                        "window_end": end.isoformat(),
                        "metadata_updated": metadata_updated,
                    },
                    ensure_ascii=False,
                )
            )
            return 0
        result = WeeklyOrchestrator(
            database,
            args.sources,
            department,
            excluded_connectors=(
                {"WechatPoolCollector"} if args.skip_wechat else None
            ),
        ).run(
            end,
            args.days,
            iso_week,
            output,
            args.audit_directory,
            args.site_data,
            window_start=start,
        )
        print(
            json.dumps(
                {
                    "status": result.status,
                    "collection": result.collection,
                    "human_actions": result.human_actions,
                    "issue_id": result.weekly.issue_id,
                    "output": str(result.weekly.output_path),
                    "audit": str(result.audit_path),
                    "site_data": (
                        str(result.site_data_path)
                        if result.site_data_path
                        else None
                    ),
                },
                ensure_ascii=False,
            )
        )
        return 0 if result.status in {"ok", "degraded"} else 1
    if args.command == "export-site-data":
        database.initialize(args.schema)
        with database.transaction() as connection:
            output = SiteDataExportAgent().export(
                connection, args.issue_id, args.output
            )
        print(json.dumps({"status": "ok", "output": str(output)}))
        return 0
    if args.command == "export-codex-brief":
        database.initialize(args.schema)
        department = load_yaml(args.department)
        issue_id = args.issue_id or ReviewService(
            database
        ).current_issue_id(department["department_id"])
        with database.session() as connection:
            output = CodexWeeklyHandoff(args.department).export_brief(
                connection, issue_id, args.output, args.limit
            )
        print(
            json.dumps(
                {"status": "ok", "issue_id": issue_id, "output": str(output)},
                ensure_ascii=False,
            )
        )
        return 0
    if args.command == "import-codex-analysis":
        database.initialize(args.schema)
        payload = json.loads(args.payload.read_text(encoding="utf-8"))
        issue_id = str(payload.get("issueId") or "")
        if not issue_id:
            raise ValueError("issueId is required")
        with database.session() as connection:
            issue = connection.execute(
                "SELECT iso_week FROM weekly_issues WHERE issue_id=?",
                (issue_id,),
            ).fetchone()
        if not issue:
            raise ValueError(f"issue not found: {issue_id}")
        output = args.output or (
            _default_root()
            / "outputs"
            / load_yaml(args.department)["department_id"]
            / f"{issue['iso_week']}.md"
        )
        with database.transaction() as connection:
            imported_issue, count = CodexWeeklyHandoff(
                args.department
            ).import_analysis(
                connection,
                args.payload,
                output,
                args.site_data,
            )
        readiness = ReviewService(database).approval_readiness(imported_issue)
        print(
            json.dumps(
                {
                    "status": "ok",
                    "issue_id": imported_issue,
                    "selections": count,
                    "ready": readiness.ready,
                    "blockers": readiness.blockers,
                    "output": str(output.resolve()),
                    "site_data": str(args.site_data.resolve()),
                },
                ensure_ascii=False,
            )
        )
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
