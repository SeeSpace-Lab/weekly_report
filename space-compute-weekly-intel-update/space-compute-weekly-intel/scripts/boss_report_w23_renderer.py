#!/usr/bin/env python3
"""Render boss-report HTML with the exact W23 visual contract.

The W23 file is the design source of truth.  This renderer deliberately reuses
its font links and CSS verbatim; weekly generators supply content only.
"""

from __future__ import annotations

from html import escape
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
W23_BASELINE = ROOT / "assets/老板版_2026-W23.html"


def _baseline_head() -> tuple[str, str]:
    source = W23_BASELINE.read_text(encoding="utf-8")
    links = "\n".join(re.findall(r'<link[^>]+(?:>|/>)(?:\s*)', source))
    style_match = re.search(r"<style>(.*?)</style>", source, re.S)
    if not style_match:
        raise ValueError(f"W23 baseline has no style block: {W23_BASELINE}")
    return links.strip(), style_match.group(1)


def _text(value: object) -> str:
    return escape(str(value), quote=True)


def _source(card: dict) -> str:
    return (
        f'<span class="src"><a href="{_text(card["url"])}" target="_blank" '
        f'rel="noopener noreferrer">Source: {_text(card["source"])} ↗</a></span>'
    )


def _body(card: dict) -> str:
    fields = (
        ("判断", "judgment"),
        ("影响", "impact"),
        ("对我们的意义", "meaning"),
        ("后续跟踪", "next_watch"),
    )
    return "\n".join(
        f'          <p><b>{label}</b> {_text(card[key])}</p>' for label, key in fields
    )


def _card(card: dict) -> str:
    family = card["family"]
    if family == "timeline":
        return f'''    <article class="card timeline-card">
      <div class="daterail">{_text(card["priority"])}<br>{_text(card["sector"])}<br>{_text(card["date_short"])}</div>
      <div>
        <h3 class="eh">{_text(card["title"])}</h3>
        <div class="body">
{_body(card)}
        </div>
        {_source(card)}
      </div>
    </article>'''

    classes = "card lead" if family == "lead" else "card"
    anchor = ""
    if card.get("anchor"):
        anchor = (
            '<span class="mono" style="color:var(--terracotta);">'
            f'{_text(card["anchor"])}</span>'
        )
    return f'''    <article class="{classes}">
      <div class="metarow"><span class="pri">{_text(card["priority"])}</span><span class="mono">{_text(card["sector"])} · {_text(card["country"])} · {_text(card["date_short"])}</span>{anchor}</div>
      <h3 class="eh serif">{_text(card["title"])}</h3>
      <div class="body">
{_body(card)}
      </div>
      {_source(card)}
    </article>'''


def _thread(thread: dict) -> str:
    item_class = {
        "policy": "ledger-item",
        "technology": "ladder-item",
        "financing": "capital-item",
    }[thread["kind"]]
    items = "\n".join(
        f'        <div class="{item_class}"><span class="mono">{_text(item[0])}</span>{_text(item[1])}</div>'
        for item in thread["items"]
    )
    return f'''    <div class="thread">
      <span class="cat">{_text(thread["label"])}</span>
      <h3 class="serif">{_text(thread["title"])}</h3>
      <div class="shape">
{items}
      </div>
      <p class="judge">{_text(thread["judgment"])}</p>
    </div>'''


def render(report: dict) -> str:
    links, style = _baseline_head()
    style = style.replace("section{margin-top:96px;}", "section{margin-top:65px;}")
    metrics = "\n".join(
        f'    <div class="metric"><div class="num serif">{_text(value)}</div><div class="lbl">{_text(label)}</div></div>'
        for value, label in report["metrics"]
    )
    proofs = "\n".join(
        f'  <div class="row"><div class="d">{_text(date)}</div><div class="t">{_text(text)}</div></div>'
        for date, text in report["proofs"]
    )
    threads = "\n".join(_thread(thread) for thread in report["threads"])
    cards = "\n\n".join(_card(card) for card in report["cards"])
    memo = "\n".join(
        f'''    <div class="col">
      <h4>{_text(column["title"])}</h4>
{chr(10).join(f'      <div class="item">{_text(item)}</div>' for item in column["items"])}
    </div>'''
        for column in report["memo"]
    )
    previous_week_review = ""
    if report.get("previous_week_review"):
        nav = "<!-- PREVIOUS_WEEK_BUTTON -->"
        if report.get("adjacent_week_href") and report.get("adjacent_week_label"):
            nav = (
                f'<a href="{_text(report["adjacent_week_href"])}" '
                f'class="previous-button">{_text(report["adjacent_week_label"])}</a>'
            )
        previous_week_review = f'''\n  <div style="padding:22px;background:var(--ivory-warm);">
    <p style="max-width:860px;font-size:16px;line-height:1.65;color:var(--ink-soft);"><b>上周重点：</b>{_text(report["previous_week_review"])}</p>
    <!-- WEEKLY_NAV_START -->{nav}<!-- WEEKLY_NAV_END -->
  </div>'''
    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>中美太空算力周报 · {_text(report["week"])}</title>
<!-- Design direction: refined industrial intelligence dossier -->
{links}
<style>{style}</style>
</head>
<body>

<!-- 1. Masthead -->
<header class="masthead">
  <div class="title serif">中美太空算力周报</div>
  <div class="meta">
    <div class="mono">{_text(report["week"])} · {_text(report["date_range"])}</div>
    <div class="mono">Compiled {_text(report["compiled"])} · Internal use</div>
  </div>
</header>
<div class="scanline mono">{_text(report["scanline"])}</div>

<!-- 2. Executive hero -->
<div class="hero">
  <div class="claim serif">{report["claim_html"]}</div>
  <div class="rail">
{metrics}
  </div>
</div>

<div class="proof">
{proofs}
{previous_week_review}
</div>

<!-- 3. Three threads -->
<section>
  <h2 class="section serif">三条<span class="u-terra">主线</span></h2>
  <div class="threads">
{threads}
  </div>
</section>

<!-- 4. Core event dossier -->
<section>
  <h2 class="section serif">核心事件 <span class="mono" style="text-transform:none;letter-spacing:0;font-size:16px;color:var(--mid-gray);">{len(report["cards"])} 条 S/A</span></h2>
  <div class="cards">

{cards}

  </div>
</section>

<!-- 5. Financing supplement -->
<section>
  <h2 class="section serif">融资其余条目</h2>
  <p class="finsup">{report["financing_supplement_html"]}</p>
</section>

<!-- 6. Action memo -->
<section>
  <h2 class="section serif">行动备忘</h2>
  <div class="memo">
{memo}
  </div>
</section>

<!-- 7. Colophon -->
<div class="colophon">中美太空算力周报 · {_text(report["week"])} · Compiled {_text(report["compiled"])} · Internal use</div>

</body>
</html>
'''


def validate(html: str, expected_cards: int) -> list[str]:
    """Return validation failures; an empty list means the structural gate passed."""
    _, baseline_style = _baseline_head()
    baseline_style = baseline_style.replace("section{margin-top:96px;}", "section{margin-top:65px;}")
    failures: list[str] = []
    style_match = re.search(r"<style>(.*?)</style>", html, re.S)
    if not style_match or style_match.group(1) != baseline_style:
        failures.append("CSS is not byte-for-byte identical to W23 baseline")
    if html.count('<article class="card') != expected_cards:
        failures.append("card count mismatch")
    for label in ("判断", "影响", "对我们的意义", "后续跟踪"):
        if html.count(f"<p><b>{label}</b> ") != expected_cards:
            failures.append(f"not every card has {label} followed by one space")
    if html.count('<span class="src"><a href=') != expected_cards:
        failures.append("source-link security attributes mismatch")
    if html.count('<div class="thread">') != 3:
        failures.append("three-thread section mismatch")
    if html.count('<div class="col">') != 3:
        failures.append("action-memo column count mismatch")
    if "上周重点：" in html:
        has_placeholder = "<!-- PREVIOUS_WEEK_BUTTON -->" in html
        has_real_nav = bool(re.search(r'<a href="(?!#)[^"]+" class="previous-button">(?:← W\d+ 周报|W\d+ 周报 →)</a>', html))
        if not (has_placeholder or has_real_nav):
            failures.append("previous-week button placeholder or deployed link missing")
    families = (
        '<article class="card lead' in html,
        '<article class="card timeline-card' in html,
        'style="color:var(--terracotta);"' in html,
    )
    if sum(families) < 3:
        failures.append("fewer than three card families")
    return failures
