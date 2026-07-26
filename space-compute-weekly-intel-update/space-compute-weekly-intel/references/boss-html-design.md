---
name: anthropic-styled-weekly-report
description: Render a polished, static-read HTML weekly intelligence report styled after anthropic.com — warm ivory parchment canvas, restrained terracotta accent, serif-plus-grotesque typographic pairing. Use this skill whenever the user asks to produce a weekly briefing, newsletter, or intelligence report as a single HTML file with an editorial, research-journal aesthetic (not a dashboard, not a slide deck, not a marketing page). Trigger phrases include: "周报 HTML", "每周资讯", "weekly briefing", "research journal", "做成 Anthropic 风格的网页", or any request that combines (a) curated event list as input and (b) a polished static webpage as deliverable.
---

# Integration Note for `space-compute-weekly-intel`

This file is the **visual design source of truth** for `老板版HTML`: color tokens, typography, spacing, tone, hard visual rules, and static-document constraints should be followed literally.

**Loading order (progressive disclosure)**: read `output-template.md` 老板版HTML 段 first to decide *what* (sections, content, event selection, financing limits, save path); then read this file to decide *how it looks* (color tokens, typography, spacing, card families, hard rules).

When this file conflicts with the space-compute weekly skill, use the following precedence:

1. Content concerns — event selection, financing limits, report sections, boss-page content scope, and save path — follow `reporting-playbook.md` and `output-template.md`. This file does not redefine them.
2. Do not ask the user to reconfirm report name/week if `SKILL.md` has already established the time window and output mode.
3. For boss-page visual direction, the **Executive Intelligence Dossier v2** rules below override the older single-column research-journal structure. Keep the Anthropic color/type restraint, but do not produce a flat article page.

# Executive Intelligence Dossier v2

The boss HTML is not merely an Anthropic-style article. It is an **executive intelligence dossier**: a static, high-polish reading page that makes the week's thesis, evidence, and next actions obvious at a glance.

Before writing HTML, commit to one clear visual direction and encode it as a short HTML comment near the top of the file:

```html
<!-- Design direction: refined industrial intelligence dossier / orbital command brief / editorial intelligence memo -->
```

Use one of these directions:

- `refined industrial intelligence dossier`: precise, material, analyst-built, with metric rails and evidence strips.
- `orbital command brief`: mission-control discipline, strong time markers, compact signal panels, no sci-fi decoration.
- `editorial intelligence memo`: magazine-quality hierarchy, one memorable cover moment, dense but calm evidence blocks.

Do not use a vague direction such as "clean", "modern", "premium", or "Anthropic style". The direction must explain what the page should feel like and what the reader will remember.

## Dossier Composition Rules

The page must have one memorable design move, but it must stay serious. Acceptable moves:

- an asymmetric first viewport with a lead claim on the left and a vertical metric rail on the right;
- a lead proof slab that turns the most important event into a compact evidence object;
- a mission-log strip showing 3-5 dated signals across policy / technology / capital;
- a dark feature block used once as the lead claim or single most important S event.

Hard requirements:

1. **First viewport = lead claim + metric rail + proof object.** The top screen cannot be only masthead + giant prose. It must include:
   - the week's 30-50 character lead claim;
   - 3-5 compact metrics, such as `事件表 143`, `正文 70`, `融资占比 30%`, `S/A 8`, `政策/科技/融资 split`;
   - one proof object: timeline strip, ranked signal list, capital strip, regulatory ledger, or source-confidence line.
2. **Every main thread needs a distinct information shape.** Policy, technology, and financing must not all be plain prose sections. Use different patterns:
   - policy: timeline rail, regulatory ledger, bill / agency / procurement strip;
   - technology: evidence stack, milestone ladder, platform / payload / chip matrix;
   - financing: capital strip, amount ladder, sector mix row, not a long company list.
3. **Core events need layout rhythm.** The usual editorial baseline is 5-8 cards, but all strongly relevant S/A events are included without a numeric cap. Use at least 3 card families and avoid long runs of the same family when the list expands.
4. **Every event card needs a visual anchor.** Use one of: amount, date, agency, law / bill number, mission name, chip / processor name, launch vehicle, customer, orbit, source tier, or next trigger.
5. **No generic article cadence.** A page that reads as `masthead -> big title -> three prose sections -> identical cards` fails, even if the colors and fonts are correct.

## Allowed Card Families

Use these reusable patterns instead of one repeated release-card:

- **Lead signal card**: one S event, larger title, 2-column body with `why it matters` and `next trigger`.
- **Timeline row**: date on the left rail, event title and implication on the right. Best for policy / launch / mission sequences.
- **Evidence stack**: 3 compact evidence bullets under one claim; each bullet has source/date.
- **Capital strip**: amount, round/deal type, company, investors/buyer, strategic meaning. Best for financing.
- **Risk/opportunity memo**: two narrow columns under one event, `机会` and `风险`.
- **Source-confidence note**: small row for source tier, primary source, secondary source, and verification status.

Use cards as editorial evidence units, not decorative containers. Do not wrap every paragraph in a card.

## Layout Rhythm Gate

Before finalizing the HTML, inspect the page at desktop width and ask:

- Does the first viewport already show the thesis, metrics, and one evidence object?
- Can a reader distinguish policy / technology / financing sections by shape before reading every word?
- Are there at least 3 layout families, and are all strongly relevant S/A events included regardless of total count?
- Is there exactly one memorable visual move?
- Does the page still feel like a serious intelligence brief, not a marketing landing page or dashboard?

If any answer is no, revise the layout before delivering.

# Anthropic-Styled Weekly Report

This skill produces **one self-contained HTML file** that reads like a research journal printed on warm stone — the visual register of anthropic.com. The deliverable is for reading, not interaction: no filters, no toggles, no JavaScript-driven UI. Typography and whitespace carry the entire experience.

The user provides a set of curated events (typically clustered by vertical) and expects a finished `.html` file. The skill's job is to translate the source material into the Anthropic visual system without drift.

---

## Design Philosophy (read before writing any code)

The aesthetic is **research journal, not dashboard**. Concretely this means:

- **Ivory parchment, not white.** The page base is `#faf9f5` — warm, not bleached. Pure white (`#ffffff`) is forbidden as a background. The warmth comes from the paper itself, not from accent color.
- **Achromatic by default.** The chromatic budget for the entire page is a single terracotta accent `#d97757`, used **sparingly** — for one or two underlines and the occasional rule, not for backgrounds, badges, or buttons.
- **Typography is the design.** A serif-plus-grotesque pairing carries the whole identity. No card shadows, no gradient meshes, no rounded pills, no purple accents. If you find yourself reaching for visual ornament, you have drifted; return to type and whitespace.
- **Word-level underline is the emphasis mechanism.** Where a magazine would use bold or color, this aesthetic uses a thick `text-decoration: underline` on a single keyword inside a headline. Use this once or twice per report — it loses meaning if repeated.
- **One dark interruption is allowed.** A single dark feature card (`#141413` background, serif display type at ~80–96px in `#faf9f5`) per report creates an editorial broadsheet break. Use it for the report's lead/cover or its single most important event. Do not use multiple dark cards.

If the user provides a serious topic (death, conflict, illness), drop the dark card and keep the page entirely light — the somber register comes from restraint, not contrast.

---

## Design Tokens (use these literally — no improvisation)

Wire all of these into CSS custom properties on `:root`. Do not introduce additional colors, additional fonts, or additional radii.

### Color

```css
:root {
  /* Surfaces */
  --ivory: #faf9f5;          /* Page base. Never use #ffffff. */
  --ivory-warm: #f0eee6;     /* Card surface on light page. */
  --ivory-deep: #e3dacc;     /* Optional second card tone, used sparingly. */
  --ink: #141413;            /* Body text and dark-card background. Never pure black #000. */
  --ink-soft: #3d3d3a;       /* Secondary text. */
  --mid-gray: #b0aea5;       /* Dividers, metadata. */
  --light-gray: #e8e6dc;     /* Hairlines, faint rules. */

  /* The one accent — use sparingly */
  --terracotta: #d97757;     /* Anthropic's signature warm accent. */

  /* Functional accents — only if absolutely needed for category color-coding.
     Use at most ONE of these per report, and prefer to skip them entirely. */
  --slate-blue: #6a9bcc;
  --olive: #788c5d;
}
```

### Typography

The page uses a **serif display + grotesque body** pairing. Use Google Fonts (free, browser-loadable) as faithful substitutes for Anthropic's proprietary Anthropic Serif / Anthropic Sans:

- **Display serif:** `"Fraunces"` (weights 400, 600) — closest free analog to Anthropic Serif; the slight humanist character matches.
- **Body sans:** `"Inter Tight"` (weights 400, 500, 600) — tight tracking, similar proportion to Anthropic Sans. Acceptable alternative: `"Geist"`.
- **Mono (metadata only):** `"JBMono"` / `"JetBrains Mono"` weight 400.

Load via:
```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,600&family=Inter+Tight:wght@400;500;600&family=JetBrains+Mono:wght@400&display=swap" rel="stylesheet">
```

Type scale (do not deviate by more than ±2px):

| Role                       | Font          | Size  | Weight | Notes                                  |
|----------------------------|---------------|-------|--------|----------------------------------------|
| Dark-card display headline | Fraunces      | 88px  | 400    | Only on `--ink` background.            |
| Section heading (H2)       | Fraunces      | 44px  | 400    | One terracotta-underlined keyword max. |
| Event headline (H3)        | Inter Tight   | 22px  | 600    | Sentence case.                         |
| Body                       | Inter Tight   | 17px  | 400    | Line-height 1.55.                      |
| Lede / pull quote          | Fraunces      | 24px  | 400    | Italic optional.                       |
| Metadata / dateline        | JetBrains Mono| 13px  | 400    | Uppercase, letter-spacing 0.08em.      |
| Category label             | Inter Tight   | 12px  | 500    | Uppercase, letter-spacing 0.12em.      |

### Spacing & Layout

- **Page shell:** max-width `1040px`, centered, for executive dossier layouts with metric rails and proof objects.
- **Reading column:** prose blocks still max at `720px`; do not let long Chinese paragraphs run across the full shell.
- **Outer page padding:** `64px` top/bottom, `32px` left/right on desktop; collapse to `48px / 20px` below 720px.
- **Section spacing:** `96px` between major sections, `48px` between events within a section.
- **Border radius:** `0` everywhere. Exception: cards inside the page (release-card pattern) may use `8px`. Buttons, badges, rules — all flat. No rounded pills.
- **Dividers:** `1px solid var(--light-gray)`. Never use `box-shadow` for separation.

### Source Links (HARD MANDATORY)

Each event card must end with a typographic source link to the original article. This is editorial provenance, not decoration.

- **Anchor text format:** `Source: <source_name> ↗`（中文上下文也用 `Source:` 前缀；`source_name` 取事件库 `source_name` 字段的简称，如 `SpaceNews` / `FCC` / `21世纪经济报道`；多来源时仅显示主来源 `source_url`，secondary 在 mono 副线一笔带过）。
- **Element:** `<a href="...">`，必须 `target="_blank"` + `rel="noopener noreferrer"`（防 tab-nabbing，并保留性能隔离）。
- **位置：** 在 card 主体内容下方，与其他 mono 副线（date / source-confidence note）同级；占独立一行，不放在段内。
- **字体与字号：** `JetBrains Mono` 14px / 400（与 mono date 同 type token）。
- **颜色：**
  - default: `--ink-soft` (`#3d3d3a`)
  - hover: `--terracotta` (`#d97757`)（唯一允许的强调色）
  - visited: 与 default 同（不区分已读，避免在静态周报里污染节奏）
- **下划线：** 始终保留 `text-decoration: underline`，颜色随文本（`text-decoration-color: currentColor`）；hover 时下划线变 terracotta。**禁止**用 box / 按钮 / pill 形状包住链接。
- **外链箭头：** 用 Unicode `↗`（U+2197）紧跟 source_name 后；不允许用 SVG 图标、Material Icons、emoji 替代。`↗` 颜色随链接文本，hover 时与链接同步变 terracotta。
- **不允许的形态：**
  - ❌ `READ MORE` / `阅读原文` / `→` 形式的按钮；
  - ❌ terracotta 填充背景的 CTA；
  - ❌ 任何 `box-shadow` / `border` / `border-radius` 包裹的链接容器；
  - ❌ 在标题或 lead 句中嵌入下划线链接（标题保持纯文本，链接固定在 card 底部）；
  - ❌ JS-driven hover 动画（`transition: color 0.15s ease` 是允许的极限）。
- **可访问性：** 鼠标用户与键盘用户都需要明确 focus state——`:focus-visible` 用 `outline: 2px solid var(--terracotta); outline-offset: 2px;`；不要用 `outline: none` 关掉默认 focus。
- **dark card 例外：** 在唯一的 dark `--ink` 背景 card 上，链接 default 用 `--ivory`、hover 用 `--terracotta`，其余规则同上。

---

## Required Document Structure

> The 7-section structure (Masthead → Executive hero/proof with previous-week extension → Three threads → Core event dossier → Financing supplement → Action memo → Colophon) and what content goes in each are defined in `output-template.md` 老板版HTML 段. This file does not duplicate that list — read output-template.md first to decide *what* each section contains, then return here for *how it should look*.

The previous-week summary is the final block inside the proof object, without its own title. Its one-week navigation button remains in normal document flow after the summary and uses the mini core-event-card shape: `--ivory-deep` background, 1px `--light-gray` border, 8px radius, compact padding, no shadow, and no `查看`. Render it as a real `<a>` with no default underline; on hover, change both text and border to `--terracotta`, and retain a visible `focus-visible` outline. The latest page labels it `← W(n-1) 周报`; the immediately previous page uses the same shape and position with `W(n) 周报 →` to return to the latest page. Section spacing is 65px; core-event card spacing remains 48px.

---

## Hard Rules — do not violate

These exist because every one of them, if broken, breaks the Anthropic register:

1. **Never use `#ffffff` as a background.** Always `--ivory`.
2. **Never use pure black `#000`.** Use `--ink` (`#141413`).
3. **Never use rounded buttons or pill-shaped badges.** Categories are typographic labels, not chips. `border-radius: 0` for any badge/label.
4. **Never use color to emphasize text inside a paragraph.** Use the terracotta underline only on 1-2 lead / section keywords. Inside body text, emphasis is italic at most.
5. **Never use more than one dark card per report.** It is the broadsheet break, not a recurring motif.
6. **Never use drop shadows, gradient backgrounds, or glassmorphism.** Surfaces differ only by their flat color.
7. **Never use generic web fonts (Inter alone, Roboto, Arial, system stack).** The serif-plus-grotesque pairing is non-negotiable. If Fraunces fails to load, fall back to Georgia; if Inter Tight fails, fall back to `-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`.
8. **Never add JS interactivity.** No filters, no tabs, no modals, no scroll animations. The deliverable is a static document.
9. **Never inline images decoratively.** This is a typographic document. Images appear only when they ARE the news (a chart, a leaked photo). When used, they sit inside the reading column or proof-object area with a mono caption below.
10. **Never use emoji as section markers or bullets.** The register does not permit it.
11. **Every event card must carry a working source link.** 见上方 `Source Links (HARD MANDATORY)` 段：anchor text 必须为 `Source: <name> ↗` 形式、`target="_blank"`、JetBrains Mono 14px、default `--ink-soft` / hover `--terracotta`。事件库中 `source_url` 为空的事件不得作为 card 候选——参 `output-template.md` 老板版HTML 段与 `reporting-playbook.md` 老板版HTML 选择规则。

---

## Workflow

When invoked, proceed in this order:

1. **Read the input.** The user will provide a list of events, usually clustered by vertical, often as Markdown or a chat dump. Identify: (a) the week's date range, (b) the verticals present, (c) the single most-important event (candidate for the dark cover card), (d) anything that belongs in the watch list rather than the main body.
2. **Confirm the report name and week-of date** with the user if not stated. Don't proceed without these — they appear in the masthead.
3. **Lock the design direction and hero proof object first.** Choose one Executive Intelligence Dossier direction, then decide the first-viewport lead claim, metric rail, and proof object before drafting prose.
4. **Draft concise thread copy and event evidence units.** Identify the 1-2 keywords that will get the terracotta underline. If you cannot find a meaningful keyword to underline, leave it unadorned — forced emphasis reads as cheap.
5. **Write the HTML in one pass.** Single file, inline `<style>` block at the top of `<head>`. No external CSS, no build step. The file should open correctly by double-clicking in a browser.
6. **Self-check against the Dossier Composition Rules and Hard Rules** before delivering. Most common drift: pure white background, rounded badges, color-coded category chips, and a flat article cadence.
7. **Save to the path required by the host skill.** Save path is defined in `output-template.md` 老板版HTML 段 (under `#### 输出与保存`); follow it there — do not duplicate the rule here.

---

## Examples of correct vs. incorrect choices

**Correct:** A section heading reads `本周 太space-compute 进展` where the word "太空算力" carries a 3px terracotta underline; the rest of the heading is plain `--ink` Fraunces.

**Incorrect:** A section heading where the entire phrase "太空算力" is colored terracotta. (Color-as-emphasis violates rule 4.)

**Correct:** Five event cards in a column, each on `--ivory-warm` with a mono date in the top-left corner and a plain text source link at the bottom: `<a href="https://spacenews.com/..." target="_blank" rel="noopener noreferrer">Source: SpaceNews ↗</a>` styled JetBrains Mono 14px, color `--ink-soft` with `text-decoration: underline`, hover transitioning to `--terracotta`.

**Incorrect:** Five event cards with terracotta "READ MORE" buttons, soft drop shadows, and rounded corners. (Violates rules 3, 6, 11, and the philosophy.) Or: cards with `Source: SpaceNews` as **plain text only** with no `<a href>` — the deliverable must be clickable, not just typographically correct (violates rule 11).

**Correct:** One dark `--ink` cover card at the top of the report containing the sentence "This week, three Chinese launch providers announced orbital data-center timelines." in Fraunces 88px, `--ivory` text, generous padding.

**Incorrect:** A dark hero card, plus a dark "key takeaways" card mid-page, plus a dark colophon. (Violates rule 5 — the dark card is precious because it's used once.)

---

## Reference

This skill encodes the design tokens from anthropic.com circa 2026: ivory `#faf9f5`, ink `#141413`, terracotta `#d97757`, serif-plus-grotesque pairing, achromatic palette with single warm accent. The Anthropic Serif / Anthropic Sans typefaces are proprietary; Fraunces and Inter Tight are the closest free analogs and what you should ship with.
