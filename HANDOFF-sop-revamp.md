# HANDOFF — S&OP Cockpit Revamp (mockup 3 approved, mockup 4 next)

**Date:** 2026-08-13 (supersedes the earlier version of this file from the same day).
**Repo:** `~/Documents/Aiwork/sop-integrated-planning` — branch `main`, remote `LaviSahu/sop-integrated-planning` (SSH).
**Why:** session hit ~200k context. Mockups 1+2 approved (fill dropped to 85% ink). Mockup 3 (levers +
5-step provenance modal) built, verified, and **approved by Lavi** — "both are fine, keep going with mockup 4."

---

## Read this first

**`SCOPE.md`** — the locked build scope, current. Do not re-derive it. §4 = lever list, §6b = the 5-step
provenance-modal pattern + chart grammar, §9 = mockup build order (each mockup needs approval before the next).

---

## Status

| Phase | State |
|---|---|
| Research, transcript, screenshots, scope lock | done (unchanged) |
| `mockups/tokens.css` contrast audit | done (unchanged) |
| `mockups/build_data.py` + `mockups/data.js` | done — now includes per-family **provenance** export (new this session) |
| **Mockup 1 — layout shell** | done, **approved**. Base-bar fill dropped to 85% ink this session (both mockups 1+2) |
| **Mockup 2 — scenario comparison** | done, **approved** |
| **Mockup 3 — levers + drill-down** | done, verified, **approved this session** |
| Mockup 4 — KPI tiles | **not started — start here** |
| Mockup 5 — margin waterfall | not started |
| Implementation | not started. Do not start it. |

---

## Immediate next step

**Build mockup 4 — KPI tiles.** Load the `dataviz` skill first (project convention, non-optional). Reuse the
`.tile` CSS class already in `mockups/tokens.css` (§ "tile: KPI tile anatomy" — label row with info affordance,
hero number, delta row, "Why?" drill-in link) rather than inventing new tile markup; it exists specifically for
this mockup. Follow the same build/verify loop as mockup 3: headless-Chrome screenshot for layout, `open
mockups/04-*.html` for Lavi's real render, ask for his verdict before mockup 5.

DESIGN.md §2 (KPI tile row) lists candidate tiles from the original frozen spec: Fill Rate ×3
(Base/Upside/Constrained), Bottleneck Resource Utilization, Upside Value Unlocked, Margin at Risk
(Constrained) — treat as a starting list, not gospel, since DESIGN.md predates SCOPE.md's visual-direction lock
(§6b) and uses a different (superseded) color-token system. Every tile's "Why?" link should open the same
provenance modal mockup 3 already built (reuse `openModal(scenario, famId, month)` where the KPI traces to a
specific family/month, or a new scenario-level rollup step where it doesn't).

---

## What changed this session

### Mockups 1+2: Base-bar fill dropped to 85% ink (approved judgment call)
`--sop-color-chart-actual` fills were reading visually heavy (near-white solid against near-black canvas).
Fixed via `fill-opacity="0.85"` on the SVG paint calls (both `01-layout-shell.html`'s `paint()` and
`02-scenario-comparison.html`'s `paintScenario()`) plus a matching `opacity:0.85` on both legend swatches —
opacity layer, not a hardcoded color, so it stays correct under the light-theme token flip.

### New: per-family provenance export (`mockups/build_data.py`)
Added `_provenance()` — for every (scenario, family, month) it now exports the real Demand → Capacity →
Rationing → Supply → Financials trail, sourced directly from the engine:
- **Demand**: `base_monthly_demand[month] × (1 + upside_uplift_pct)` when the scenario applies uplift.
- **Capacity**: per touched resource, `ResourceLoad` (load/available/utilization/is_bottleneck).
- **Rationing**: calls `constrain._allowed_units_this_month` directly (the actual authoritative rationing
  decision — greedy by descending unit margin) rather than re-deriving it; only the presentational trail
  (rank, cumulative/remaining hours) is recomputed from that authoritative result, so the rationing rule lives
  in exactly one place.
- **Supply / Financials**: the real `SupplyLine`/`FinanceLine` objects via `jsonable()`.

Verified arithmetically (not just "ran without error"): confirmed `remaining_before − granted = remaining_after`
holds, and found a real rationed case (FAM-DRY, rank 3 of 3, capped at whatever capacity was left) to prove the
"protect highest-margin business first" rule actually renders, not just the trivial unconstrained case.

`data.js` regenerated: 712,821 bytes (up from a few hundred KB — the provenance block is the bulk of the
growth; 6 families × 12 months × 3 scenarios × ≤4 resources).

### New: `mockups/03-levers-drilldown.html`
- **Levers panel** (SCOPE §4): Tier 1 visible by default, Tier 2 behind a native `<details>` "Advanced"
  disclosure. Every slider renders **disabled** with an honest inline note — no live recompute exists yet (no
  JS port of the engine), so a draggable-but-inert lever would be a lie. Where a real Base-scenario reference
  number exists (e.g. installed hours per resource), the caption shows it; everything else states its unit and
  that Base = 0% by construction. **Confirmed by Lavi — keep disabled, don't fake interactivity.**
- **Drill-down grid**: family × month table of fill rate %, sorted by margin (same order as mockup 2's family
  panel). Cells tint red on real unmet demand (not "was rationed this month" — those differ: opening inventory
  can absorb one month's production shortfall with zero customer impact, which the grid correctly shows, e.g.
  FAM-DRY was rationed in March but still hit 100% fill because inventory covered it).
- **5-step provenance modal**: reuses tokens.css's pre-built `.modal`/`.modal-scrim`/`.step-connector` base
  classes (already designed for exactly this — comment says "connector between the 5 numbered provenance
  steps"). **Confirmed interpretation**: 5 numbered steps (Demand/Capacity/Rationing/Supply/Financials), KPI as
  a closing tie-back line under step 5, not a 6th numbered step.

### Verification method (headless Chrome, no puppeteer available)
Syntax-checked the inline script with `node --check` (parse-only, catches typos without needing a DOM). For
runtime verification, copied the mockup to the scratchpad **with `data.js`/`tokens.css` copied alongside it**
(the first attempt failed with a misleading `undefined.resources` error that was actually a missing-sibling-file
problem in the test harness, not a real bug — worth remembering if this pattern recurs), injected a
`window.onerror` handler, and simulated a real `.click()` on a grid cell (not a fake global function call — an
earlier attempt to call `openModal(...)` directly failed because it's scoped inside the IIFE, not global).
Caught one real bug this way: `.step__formula` used `white-space: nowrap` + `overflow-x:auto`, which clipped
long lines and rendered a persistent horizontal-scrollbar bar under each formula box in headless Chrome. Fixed
by switching to normal wrapping (`white-space: normal; word-break: break-word`) and widening the modal
(640px → 720px). Re-verified clean after the fix. Also checked light theme + the Advanced disclosure open —
both render correctly. No raw hex/rgb colors introduced outside `tokens.css` tokens (grepped to confirm), so no
new categorical palette needed the `dataviz` validator.

---

## Engine facts (unchanged, still current — not re-derived here)

See git history (commit `09217a2`) for full engine-facts and the architecture-fork section (client-side
lever-drag recompute → JS port, Python as reference, golden-fixture tests). Two open questions for Lavi remain
**unanswered** (not raised again this session — still open):
1. Planner override / HITL — in scope, and how deep? (`SCOPE.md` §8)
2. The JS-port fork — confirm the golden-fixture approach. Relevant now that mockup 3 made the "levers don't
   recompute yet" gap concrete and visible on screen.

### Blocker on Stage-4 goal (unchanged)
`data/families.json` has no revenue/margin targets. Stage 4 needs an explicit target per scenario plus a
gap-to-plan line in $ and % — new input data, not just a new chart. Raise before claiming Stage 4.

---

## Next jobs, in order

1. **Mockup 4 — KPI tiles** (see "Immediate next step" above). Start here.
2. Mockup 5 — margin waterfall.
3. Only after Lavi approves all 5: revisit the two open engine-architecture questions before implementation.

---

## Suggested skills

- **`dataviz`** — load again before touching mockup 4, non-optional for this project.
- **`/brief`** or **`/terse`** — Lavi runs sessions compressed; pick whichever is active or ask.
- **`artifact-design`** — KPI tile anatomy/hero-number layout is relevant again for mockup 4.
- Skip `code-review` / `simplify` until implementation actually lands.

---

## Working style (carry forward, unchanged)

- **Judge files and diffs, never prose.** Verify every claim by running it — this session's headless-Chrome
  verification loop (syntax check → runtime click-simulation → visual screenshot) is the pattern to repeat for
  mockup 4, not just "it looks like it should work."
- **Read the sources yourself when they're the design input** — this session read `constrain.py`/`finance.py`/
  `demand.py`/`capacity.py` in full before writing the provenance export, rather than guessing the formulas.
- Lavi is terse and decisive, pushes back on badly-scoped work, wants to be grilled. Recommendation + one next
  action, not a survey. He approves fast when the work is honest about its own gaps (e.g. disabled levers) —
  don't oversell mockup capability to make it look more finished than it is.
- **Do not implement until he confirms.** Still true, still unconfirmed.

---

## Git state — uncommitted

Nothing has been committed this session (project convention: never commit without being asked). Working tree
currently has:
```
 M mockups/01-layout-shell.html
 M mockups/02-scenario-comparison.html
 M mockups/build_data.py
 M mockups/data.js
?? mockups/03-levers-drilldown.html
```
Decide at the start of next session whether to commit (Lavi has approved mockups 1–3, so there's a reasonable
case for it) — don't commit automatically just because this handoff exists.

---

## Privacy

`research/wispr-transcript.md` contains real names and a private startup's commercial details.
**Local commits only — do not push to any public remote without redacting.**
