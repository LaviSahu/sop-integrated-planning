# HANDOFF — S&OP Cockpit Revamp (mockup 2 built, unverified in browser)

**Date:** 2026-08-13.
**Repo:** `~/Documents/Aiwork/sop-integrated-planning` — branch `main`, remote `LaviSahu/sop-integrated-planning` (SSH).
**Why:** session hit ~220k context. Mockup 1 is built, screenshotted, and fixed. Mockup 2 is built and
geometry-fixed but **the last round of fixes was never re-rendered** — the `open` command that would have
shown it in Chrome was interrupted before it ran. Verify that first.

---

## Read this first

**`SCOPE.md`** — the locked build scope, current. Do not re-derive it. §7 governs "hand-checkable arithmetic"
(the corrected reading of the transcript's "Excel" line — see below); §8b gives the chart grammar; §9 gives the
mockup build order.

---

## Status

| Phase | State |
|---|---|
| Research, transcript, screenshots, scope lock | done (unchanged from prior handoff) |
| `mockups/tokens.css` dark-primary rewrite | done, then **contrast-audited and fixed** this session (below) |
| `mockups/build_data.py` + `mockups/data.js` | done — real engine output, zero hand-typed numbers |
| **Mockup 1 — layout shell** | done, screenshotted in both themes, defects fixed, DOM-verified |
| **Mockup 2 — scenario comparison** | built, geometry-fixed, **not yet re-screenshotted** — do this first |
| Mockup 3 — levers/drill-down | not started |
| Mockup 4 — KPI tiles | not started |
| Mockup 5 — margin waterfall | not started |
| Implementation | not started. Do not start it. |

---

## Immediate next step

```bash
cd ~/Documents/Aiwork/sop-integrated-planning
open mockups/02-scenario-comparison.html   # or screenshot headless, see mockup 1's session for the pattern
```

Look specifically at the three geometry fixes made right before the interrupt (all unverified):
1. **Structural-comparison bars** (`drawLevels`) — scenario labels moved into a left gutter (`GUTTER = 74`)
   instead of printing inside the bar, so a zero-length bar (e.g. Base's `$0` lost margin) doesn't collide
   label-on-value. Check Jan–Dec still reads cleanly at zero-width.
2. **Variance panel** (`drawVariance`) — Base now prints a muted "reference" label instead of a meaningless
   "▬ no change" bar against itself; value labels right-aligned in a reserved strip.
3. **Family drilldown bars** (inside `renderFamilies`) — same gutter treatment applied, `FW/FG/FR` constants,
   was previously using the old flush-left geometry that mockup 1's fix pattern had already moved away from.

The last screenshot on file (`cmp-dark.png` in this session's scratchpad, now gone — it was in
`/private/tmp/claude-501/.../scratchpad/`, which does not persist across sessions) showed label/value collisions
in exactly the rows these three fixes target. **Re-render before trusting the file.**

---

## What changed this session

### 1. Transcript literalism corrected (`SCOPE.md` §7, `HANDOFF` note)
Lavi flagged: *"take reference on the idea, not take every word like Excel literally."* The governing quote —
*"I should be able to do it on Excel and the same thing should come out as output"* [56:33] — was being read as
a spreadsheet-export requirement. Corrected in `SCOPE.md` §7: **"Excel" means hand-checkable arithmetic**, not
a spreadsheet feature. Every number on screen must be re-derivable by a human from inputs visible on screen, with
the operation shown — that's the actual bar. Same correction applied to the acceptance-test line in this file.
General principle now stated in SCOPE: take the transcript's underlying intent, don't spec incidental wording.

### 2. `tokens.css` — contrast-audited, not just aesthetic (both themes)
Ran the `dataviz` skill's `validate_palette.js` plus a manual WCAG contrast pass on every text/ink/status token
against every surface it's actually used on (surface, canvas, surface-raised in dark; surface, canvas in light).
**Failures found and fixed:**
- Dark `text-muted` `#6b7280` → `#828997` (was 3.73:1 on surface, under AA; now 4.88–5.60:1)
- Dark `ink-faint` `#565b68` → `#646a78` (was 2.66:1, under the 3:1 mark floor; now 3.17–3.33:1)
- Dark `info` `#60a5fa` → `#22d3ee` (was ΔE 0.3 deutan / 10.2 normal from brand purple — indistinguishable;
  cyan is ΔE 11.4 / 21.2, 9.5–9.99:1 on surface)
- Light `text-muted` `#868c98` → `#666d79` (was 3.38:1 on white, under AA; now 4.87–5.21:1)
- Light `ink-soft` `#9096a3` → `#767c8a` (was 2.97:1, under mark floor; now 3.91–4.18:1)
- Light `ink-faint` `#c7cad2` → `#858b98` (was 1.64:1 — invisible as a mark; now 3.04–3.25:1)

All changes are commented in-place in `tokens.css` with the before/after ratio. Verified with a script pass
(not eyeballed) — every text token ≥4.5:1, every mark/status token ≥3:1, in both themes, against every surface
it's used on. This is a **shared file** — both mockups inherit these fixes automatically.

### 3. Mockup 1 — `mockups/01-layout-shell.html` (done, verified)
Headline verdict band + binding-constraint callout, 4 stat tiles with ▲▼ variance, 3×3 small-multiples grid
(rows = demand-vs-shipped / revenue / bottleneck utilization, columns = Base/Upside/Constrained, shared
y-domain per row), narrative rail, table-view collapse, hover tooltips with the arithmetic in the footer,
light/dark toggle. Verified: headless Chrome render inspected in both themes, zero console errors, DOM
assertions pass (9 chart cells, 108 hover hit-targets, 7 legend items, 4 tiles).

**Defects found by looking at the actual render and fixed:**
- Demand/shipped bars read as a picket fence — changed to plan-as-full-width-frame with actual at 50% inside,
  plus a dedicated red cap for unmet demand (visible Apr/May/Dec on Constrained).
- Fill-rate delta was labelled `−0.9%` when it's percentage points, not a percent change — now `−0.91 pp`.
- Upside was grey-fill in bars but dashed in lines — inconsistent scenario identity. Now consistent everywhere:
  Base = full ink, Upside = soft ink, Constrained = hatched (bars) / dashed (lines, since a stroke can't hatch).

**Open judgement call, not yet decided:** Base's solid-white bars are visually heavy against near-black.
IBCS-correct, but ask Lavi: drop actual fills to ~85% ink, or leave as-is?

### 4. Mockup 2 — `mockups/02-scenario-comparison.html` (built, unverified — see "Immediate next step")
Structural comparison per SCOPE §8b's prescribed grammar: **horizontal bars** for structural comparison (not
columns — those are reserved for time series), levels-panel + separate variance-vs-Base panel side by side,
bullet graphs with graded safe/strained/critical bands (not a binary >100% flag) for bottleneck utilization and
fill rate, family-level margin drilldown showing what rationing costs each product family. Four preset buttons
(S0 Base, S1 Constrained, S2 Upside, S3 Invest) per SCOPE §3 — **S3 Invest is shown disabled**, not faked,
because the engine has no added-hours lever yet. Colour reserved for variance; scenario identity is fill pattern
(solid/hatched/soft) throughout, matching mockup 1.

**Not yet checked in a real browser after the last edit** — do this before showing Lavi.

---

## Engine facts (unchanged, still current)

- 9 modules: `models`, `datagen`, `demand`, `capacity`, `constrain`, `finance`, `kpi`, `dashboard`, `cli`.
- Scenarios are a hardcoded enum (BASE/UPSIDE/CONSTRAINED), parameters as literal tables in `datagen.py`.
  No config file, no CLI overrides, no lever surface of any kind exists in the engine today.
- `mockups/build_data.py` (new this session) is the bridge: calls the real engine
  (`cli._load_or_generate_dataset`, `cli.run_all_scenarios`, `kpi.compute_kpis`, `dashboard.build_context`),
  then aggregates monthly revenue/margin from the per-`(family, month)` `FinanceLine`s — `build_context()`
  alone doesn't expose those — and writes `mockups/data.js` as `window.SOP_DATA`. Regenerate with:
  ```bash
  PYTHONPATH=src python3 mockups/build_data.py
  ```
  Every number both mockups render traces back to this file. No hand-typed figures anywhere in the mockups.
- `constrain.py`'s rationing loop is sequential/stateful (inventory carry + margin-priority order) — still the
  one piece where a naive JS port would silently differ, if/when the lever-drag recompute work happens.

### The architecture fork (still open, still unconfirmed by Lavi)
Client-side lever-drag recompute means porting the planning math to JS. Recommendation on the table: port to
JS, Python stays the reference implementation, golden-fixture test asserts JS reproduces Python's numbers for
the 4 presets. Not yet confirmed.

---

## Next jobs, in order

1. **Re-render mockup 2, inspect it, fix whatever the screenshot shows** (see "Immediate next step").
2. **Show both mockups 1 and 2 to Lavi for approval** before starting mockup 3 — SCOPE §9 requires each mockup
   approved before the next starts. Neither has been shown yet this session.
3. Resolve Base's bar-weight judgement call (mockup 1) while you're there.
4. Mockup 3 — levers + drill-down interaction (the 5-step provenance modal is the centrepiece per SCOPE §6b).
5. Mockup 4 — KPI tiles.
6. Mockup 5 — margin waterfall.

### Two open questions for Lavi (unchanged, still unanswered)
1. **Planner override / HITL** — in scope, and how deep? (`SCOPE.md` §8)
2. **The JS-port fork** — confirm the golden-fixture approach above.

### Blocker on Stage-4 goal (unchanged)
`data/families.json` has no revenue/margin targets. Stage 4 needs an explicit target per scenario plus a
gap-to-plan line in $ and % — that's new input data, not just a new chart. Raise it before claiming Stage 4.

---

## Suggested skills

- **`dataviz`** — already loaded and used this session (palette validation, form/chart-grammar rules). Load it
  again before touching mockup 3+ — non-optional for this work per the project's own convention.
- **`/brief`** — this session ran in brief mode; Lavi prefers it.
- **`artifact-design`** — layout/visual fundamentals, relevant for the provenance-modal work in mockup 3.
- Skip `code-review` / `simplify` until implementation actually lands.

---

## Working style (carry forward, unchanged)

- **Judge files and diffs, never prose.** Verify every claim by running it — this session's contrast fixes were
  script-validated, not eyeballed, after finding early WCAG failures on colors that looked fine by eye.
- **Read the sources yourself when they're the design input.** Applies equally to the transcript wording itself
  now — this session's main correction was Lavi catching over-literal reading of one line.
- Lavi is terse and decisive, pushes back on badly-scoped work, wants to be grilled. Recommendation + one next
  action, not a survey.
- **Do not implement until he confirms.** Still true, still unconfirmed.

---

## Privacy

`research/wispr-transcript.md` contains real names and a private startup's commercial details.
**Local commits only — do not push to any public remote without redacting.**
