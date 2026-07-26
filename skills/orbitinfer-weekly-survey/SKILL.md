---
name: orbitinfer-weekly-survey
description: Run the local OrbitInfer weekly research-survey workflow without an external model API. Use when Codex needs to collect the fixed source pool, curate the week’s important papers and WeChat articles, produce evidence-constrained Chinese deep-read cards, write them back to the local review site, or prepare the Monday review draft.
---

# OrbitInfer Weekly Survey

Run every stage from `D:\code\weekly_report`. Use Python only for collection,
normalization, rule-based shortlisting, storage, validation, and rendering. Use
Codex itself for final selection, source review, synthesis, and Chinese writing.
Never request, read, configure, or call an external model API key.

## Workflow

1. Inspect `git status --short` and preserve unrelated changes.
2. Confirm Docker Desktop is available. Start the existing WeRSS container with
   `docker start weekly-report-werss` when it is stopped. Verify
   `http://127.0.0.1:8001/` responds.
3. Set `WECHAT_FEED_BASE_URL=http://127.0.0.1:8001/feed` and
   `WEEKLY_FETCH_FULLTEXT=1`. Do not set any `WEEKLY_LLM_*` variable.
4. Run:

   ```powershell
   .\.venv\Scripts\weekly-intel.exe run-weekly --days 7
   .\.venv\Scripts\weekly-intel.exe export-codex-brief
   ```

   `run-weekly` defaults to the previous complete Asia/Shanghai calendar week:
   Monday 00:00 through Sunday 23:59:59, named with that week's ISO number. If
   it returns `skipped_protected`, the issue is already approved or published;
   stop the run without exporting a brief or changing any selected content.
   The command may normalize that issue's date metadata to the closed calendar
   week, but it must never replace its approved selections.
5. Read `runs/codex/current-brief.json`. The exporter must reserve eight
   fixed-pool WeChat candidates whenever at least eight are available in the
   collection window. Review all eight, but do not force any of them into the
   report. Treat scores and the reserved pool as a shortlist, not the editorial
   decision.
6. Inspect the newest `runs/*.json` collection audit. If OpenReview reports
   `challenge_required`, do not retry the challenge in a loop. Continue with
   arXiv and Crossref candidates, and verify any claimed top-venue status
   against the conference's official accepted-paper/program page. Record
   OpenReview as unavailable for that run rather than treating the whole survey
   as failed. GitHub releases collected through the official Atom feed are
   acceptable first-party release evidence when API credentials are absent.
7. Select at most eight items and at most thirty minutes total. Prefer:
   accepted top-venue work, important paper revisions, consequential
   benchmarks/datasets/framework releases, high-quality fixed-pool WeChat
   syntheses, and research strongly adjacent to OrbitInfer.
8. Reject routine arXiv churn, generic AI news, unverified promotional claims,
   minor releases, and weakly related satellite/network material.
9. Open each selected primary source. Use WeChat only as interpretation; verify
   factual claims against the paper, official project, conference page, dataset,
   or repository. Never infer methods or results from the title.
10. Write `runs/codex/current-analysis.json` using
   [references/analysis-schema.md](references/analysis-schema.md).
11. Import and validate:

   ```powershell
   .\.venv\Scripts\weekly-intel.exe import-codex-analysis `
     runs\codex\current-analysis.json
   .\.venv\Scripts\python.exe -m unittest discover -s tests -v
   npm.cmd --prefix site run build
   ```

12. If the importer reports blockers, fix the evidence or omit the unsupported
    item. Do not lower the quality threshold.
13. Start the local review services:

    ```powershell
    powershell.exe -ExecutionPolicy Bypass -File `
      scripts\start_local_review.ps1
    ```

    Leave the issue in `review`; never approve, push, or publish without the
    researcher’s explicit confirmation.
14. Report the candidate count, selected count, source failures, reading time,
    readiness, and the local review URL in the Scheduled result.

## Editorial rules

- Write Chinese for immediate comprehension; retain the original English title
  as the main card title.
- State the concrete mechanism in `methodZh`, not a field label or broad topic.
- State reported metrics, comparison baselines, or qualitative findings in
  `resultZh`; distinguish abstract claims from independently verified results.
- Put source-specific support in `evidence`. When only an abstract or release
  note is available, say so in `limitations` and lower confidence.
- Keep confidence below `0.75` without full text or an official detailed source.
- Never reuse another article’s interpretation verbatim without attribution.
- Do not include venue calendar updates in the department weekly report.
