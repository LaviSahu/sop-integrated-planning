# HANDOFF — S&OP Cockpit build authorized: mockup 4 approved, 5 approved, green-light to implement

**Date:** 2026-08-13 (supersedes the earlier version of this file from the same day).
**Repo:** `~/Documents/Aiwork/sop-integrated-planning` — branch `main`, remote `LaviSahu/sop-integrated-planning` (SSH `github-lavisahu`). Clean, pushed.
**Why this version:** mockup 4 (KPI tiles) is now **approved** — the design rejection is resolved. Lavi's verdict: *"thats fine we will build and then do new version later"* — implementation is authorized, with a *future* redesign (not now).

---

## Read this first

**`SCOPE.md`** — the locked build scope, current. §4 = lever list, §6b = the 5-step provenance-modal pattern + chart grammar, §8 = build/mockup order, §9 = mockup build order.

**New this session:** mockup 4 was **rebuilt + approved** (the earlier hero-tile grid was rejected; see below).

---

## Status — implementation GO

| Phase | State |
|---|---|
| Research, transcript, screenshots, scope lock | done |
| `mockups/tokens.css` contrast audit | done |
| `mockups/build_data.py` + `mockups/data.js` | done |
| **Mockup 1** — layout shell | done, **approved** |
| **Mockup 2** — scenario comparison | done, **approved** |
| **Mockup 3** — levers + drill-down | done, **approved** |
| **Mockup 4** — KPI tiles | **done, REBUILT, APPROVED** (commit `28967ec`) |
| **Mockup 5** — margin waterfall | done, verified (click-sim 10/10), contrast-fixed, **folded into "we'll build"** |
| **Implementation** | **GO — authorized by Lavi** |

**Lavi's exact words (this session):** *"thats fine we will build and then do new version later"* — build the cockpit now; a new version/redesign comes later. Do not start a mockup redesign now.

---

## The mockup-4 redesign (this session, all committed + pushed)

Mockup 4 on disk was already the chart-panels build (committed `145c895`), **not** the hero-tile grid the earlier HANDOFF described as "rejected." Confirmed against git history. So the redesign made **that** bolder — not the rejected tiles.

**What changed (presentation only — data layer, rollups, 5-step modal untouched):**
1. **Live panel notes** — each panel's static grey note is now a computed verdict (the exact $8.42M upside / $531.7k at risk, the peak month, "the other 9 months cost nothing"). Fires from the same engine data as the charts.
2. **Fill bullets** — hover shows the **real 12-month per-family fill sparkline** (new `familyMonthlyFill`/`fillSvg` from `D.provenance`) + a 5-family breakdown tooltip.
3. **Load curve** — Apr/May/Dec flagged as the rationing months (red track + marker, `RATION = [4,5,12]`), "rations Dryers" tooltip, "Apr · May · Dec over 100% — the only months that cost shipped units" caption.
4. **Margin bars** — rise in sequence on load (`riseIn` keyframes) + **count-up** to final figures (`animateCount`).
5. **Upside bars** — count-up delta, same rise.
6. **Explicit drill links** ("Dryers, 3 months… →", "Open the rollup →") on the duo panels — the click-affordance was previously invisible.
7. Fixed the stale "six tiles" doc comment.

**Verified:** node syntax check → headless-Chrome click-sim **9/9** (sparkline popover, modal open/close, rollup rows, flags, drill links, live note) → dark + light screenshots → impeccable detector (only 3 pre-existing items, none from the new code). Committed `28967ec`, pushed. Working tree clean.

**Design process:** `impeccable` skill (`bolder` command) loaded per prior HANDOFF. Craft-floor rules honored: no new primitives, amplify the system's own vocabulary (DESIGN.md palette + tokens.css), no decorative sparkline (real data only), one authored motion moment (rise-in), count-up uses tabular numerals so the grid doesn't jitter.

---

## Immediate next step — IMPLEMENTATION (the big task)

Build the cockpit: **one self-contained `output/dashboard.html`** (inline CSS + vanilla JS + inline SVG, zero CDN, zero API keys) per DESIGN.md, assembled from the approved mockups. Build via `Makefile`; outputs in `output/`.

**Assembly map (mockup → section):**
- Mockup 1 (`01-layout-shell.html`) — layout shell + theme system.
- Mockup 2 (`02-scenario-comparison.html`) — demand-vs-supply chart.
- Mockup 3 (`03-levers-drilldown.html`) — levers + 5-step provenance modal.
- Mockup 4 (`04-kpi-tiles.html`) — KPI tile row / headline band.
- Mockup 5 (`05-margin-waterfall.html`) — the margin waterfall (§8b).

**Two open engine questions to revisit BEFORE writing code** (from `09217a2`, still unanswered — ask Lavi, don't assume):
1. **Planner override / HITL** — in scope, and how deep? (`SCOPE.md` §8)
2. **The JS-port fork** — confirm the golden-fixture approach.

**Also before implementation:**
- `mockups/03-levers-drilldown.html` + `mockups/04-kpi-tiles.html` are still untracked (`.claude/` gitignored — impeccable skill, local only). The work is in `04` (committed); `03` may still be untracked — check `git status`.
- **`data/families.json` has no revenue/margin targets** — Stage 4 (gap-to-plan) needs a target per scenario + gap line. New input data, not a new chart. Raise before claiming Stage 4.

---

## Verification method (carry forward — judge files, never prose)

Syntax check (`node --check` on extracted inline script) → headless-Chrome screenshot → **click-simulation harness** (append a `<script>` into a copy of the HTML, `.click()` every interactive element, write results to `document.title`, read via `chrome --headless --dump-dom`). This caught a real bug a screenshot alone missed (margin-at-risk $0.00). Full harness pattern in the prior HANDOFF / this session's shell history. Run it for every interactive element in the built dashboard.

---

## Suggested skills

- **`impeccable`** (project-scoped, `.claude/skills/impeccable`) — for the built `dashboard.html`, run `critique`/`bolder` if needed; for now the direction is approved, so only a light `polish` before shipping.
- **`dataviz`** — project convention for any chart, non-optional (mark specs).
- **`update-config`** — if any settings/hooks change needed (none known).
- **`/handoff`** — this session is near context limit; the build should run in a **fresh session** that auto-loads this doc after `/clear`.

---

## Working style (carry forward, unchanged)

- **Judge files and diffs, never prose.** Click-sim over screenshot-only verification.
- **A working build is not an approved design.** Verification proves correctness, not taste. Don't conflate in status reporting.
- Lavi is terse and decisive, pushes back on badly-scoped work, wants to be grilled. Design feedback is blunt ("AI slop") — take it as a direct, actionable signal.
- **Do not start a redesign now** — Lavi approved the current build; "new version" comes later.
- Commit handoffs locally; nothing pushes automatically.

---

## Git state — clean, pushed

- `28967ec` — mockup 4 bolder redesign (approved)
- `c9efc01` — prior handoff
- `effe3d7` — mockup 5

Working tree clean. `.claude/` untracked + gitignored (impeccable skill, local only).

---

## Privacy

`research/wispr-transcript.md` contains real names and a private startup's commercial details.
**Local commits only — do not push to any public remote without redacting.**
