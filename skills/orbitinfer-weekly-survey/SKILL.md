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

5. Read `runs/codex/current-brief.json`. Treat its scores as a shortlist, not
   the editorial decision.
6. Select at most eight items and at most thirty minutes total. Prefer:
   accepted top-venue work, important paper revisions, consequential
   benchmarks/datasets/framework releases, high-quality fixed-pool WeChat
   syntheses, and research strongly adjacent to OrbitInfer.
7. Reject routine arXiv churn, generic AI news, unverified promotional claims,
   minor releases, and weakly related satellite/network material.
8. Open each selected primary source. Use WeChat only as interpretation; verify
   factual claims against the paper, official project, conference page, dataset,
   or repository. Never infer methods or results from the title.
9. Write `runs/codex/current-analysis.json` using
   [references/analysis-schema.md](references/analysis-schema.md).
10. Import and validate:

   ```powershell
   .\.venv\Scripts\weekly-intel.exe import-codex-analysis `
     runs\codex\current-analysis.json
   .\.venv\Scripts\python.exe -m unittest discover -s tests -v
   npm.cmd --prefix site run build
   ```

11. If the importer reports blockers, fix the evidence or omit the unsupported
    item. Do not lower the quality threshold.
12. Start the local review services:

    ```powershell
    powershell.exe -ExecutionPolicy Bypass -File `
      scripts\start_local_review.ps1
    ```

    Leave the issue in `review`; never approve, push, or publish without the
    researcher’s explicit confirmation.
13. Report the candidate count, selected count, source failures, reading time,
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
