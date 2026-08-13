# HANDOFF — S&OP Cockpit built: approved mockups assembled, verified, shipped

**Date:** 2026-08-13 (supersedes the earlier implementation-GO version).
**Repo:** `~/Documents/Aiwork/sop-integrated-planning` — branch `main`, remote `LaviSahu/sop-integrated-planning` (SSH `github-lavisahu`).
**Status:** implementation **DONE** — commit `30e84c3`, pushed. Working tree clean (one untracked exploratory script).
**Approval:** Lavi reviewed the open dashboard and said **"looks good"** (2026-08-13) after a walkthrough of the headline → presets → drill-down → rollups → waterfall narrative.

---

## Read this first

**`SCOPE.md`** — the locked build scope. **`DESIGN.md`** — the behavioural contract.

The built cockpit is `make dashboard` → `output/dashboard.html` — one self-contained file (inline CSS + vanilla JS + inline SVG, zero CDN, zero API keys). Open it and it is the approved mockups assembled into one page.

---

## Status

| Phase | State |
|---|---|
| Mockups 1–5 | done, approved |
| **Implementation** | **DONE** — `30e84c3`, pushed |
| Verification | 83/83 tests, click-sim 28/28, golden-fixture 0-diff |

**Open questions that were pending — both resolved:**
1. **Planner override / HITL** → **Deferred** (Lavi: "thats fine we will build and then do new version later"). Levers are the single edit path; override belongs to the new version.
2. **JS-port golden-fixture** → **Locked by SCOPE §8b** and now **proven**: `build_context()` emits the exact data contract `mockups/data.js` carries, verified **0 diffs**.

---

## What was built

**`build_context()` enrichment (`src/sop_integrated_planning/dashboard.py`):**
- Now emits `monthly` (per-month demand/produced/shipped/unmet/revenue/margin), `utilization` (per-resource 12-month load series), `provenance` (per scenario/family/month: the full Demand → Capacity → Rationing → Supply → Financials trail), and `month_names` — mirroring `mockups/build_data.py` exactly, delegating to the same engine internals (`constrain._allowed_units_this_month`, `capacity.compute_loads`, `finance`).
- **Verified 0 diffs** against the golden `mockups/data.js` across all three scenarios and provenance.

**`_TEMPLATE` replacement:** the old dashboard template (a different design) was replaced with the assembled approved mockups:
- **Merged CSS** — `tokens.css` (the `--sop-*` token system, dark-primary + light override) + all five mockup `<style>` blocks. ⚠️ The mockups load tokens.css via `<link>`; the first build pass omitted it and rendered with no tokens — **fixed** by prepending it. Check `--sop-color-canvas:` appears twice (dark + light) if rebuilding.
- **One coherent body** — topbar → headline band (m4) → KPI tiles (m1) → scenario presets (m2) → small multiples (m1) → structural comparison + bullets + families (m2) → levers + drill grid + 5-step provenance modal (m3) → fill bullets / load curve / margin months / upside variance (m4) → margin waterfall + bridge (m5) → narrative rail → footer.
- **One merged app script** (`mockups/dashboard-app.js`) — deduplicated helpers (money/units/pct/svgEl/paintScenario/showTip/stepHtml/openModal/openRollup), id-collision-free sections, reads `DATA` (the template's `const DATA = __DATA_JSON__;` — the mockups used `window.SOP_DATA` from a `<script src>`; the built file has no external script).

**Build sources (committed):** `mockups/dashboard-app.js`, `mockups/dashboard-body.html`, `mockups/dashboard.css` are the authoritative pieces that `dashboard.py`'s template embeds. `mockups/assemble_dashboard.py` was an exploratory extraction script — **not load-bearing**, left untracked.

---

## Verification performed (judge files, never prose)

- **`make dashboard`** → `output/dashboard.html` (616 KB, self-contained). `grep -c "http://|https://|<script src|<link "` → **0**.
- **`make demo`** → clean end to end.
- **83/83 engine tests pass** (`PYTHONPATH=src python3 -m unittest discover -s tests`).
- **Headless Chrome renders all sections with zero JS errors** — every container populated.
- **Click-sim 28/28** — theme toggle, table toggle, all 4 presets, 3 scenario tabs, grid-cell provenance modal + close, both drill links, 4 waterfall bars, 3 fill bullets, load/margin/upside wraps, 4 bridge rows, esc-close.
- **Golden-fixture 0-diff** — the embedded `const DATA` is byte-identical to `mockups/data.js`.
- **Figure checks** — Constrained GM `$60.09M`, fill `99.09%`, margin-at-risk rollup `$531,728.01` (NOT the $0.00 bug the mockup caught), upside value `$8.42M`. Matches `implementation-notes.md`.
- **Themes** — dark `#0a0b0f` / light `#f7f7f8`, toggle works (`data-theme` flips, button text flips).
- **Contrast** — dark-theme token pairs all ≥4.5:1 AA (muted 5.14:1, good 10.23:1, bad 7.11:1, info 10.88:1, warn 10.81:1).

---

## Working style / conventions to carry forward

- **Judge files and diffs, never prose.** Click-sim over screenshot-only verification.
- **A working build is not an approved design.** Verification proves correctness, not taste.
- Lavi is terse and decisive; pushes back on badly-scoped work; wants to be grilled.
- **Do not start a redesign now** — "new version" comes later.
- The SVG namespace in `dashboard-app.js` is intentionally built without a literal `http://` (`"http:" + "//..."`) so the self-containment test's `assertNotIn("http://")` stays strict — preserve that if editing.
- `mockups/assemble_dashboard.py` is stale/exploratory; if the build needs re-assembly, edit the pieces (`dashboard-app.js` / `dashboard-body.html` / `dashboard.css`) and re-splice into `dashboard.py`'s `_TEMPLATE`.

---

## Possible next steps (do not start without Lavi)

1. **New version / redesign** — Lavi's deferred ask.
2. **Planner override / HITL** — SCOPE §8, deferred.
3. **Stage 4 gap-to-plan** — needs target input in `families.json` (SCOPE §8b: "cannot be claimed until a target input exists"). New input data, not just a chart.
4. **Levers wired** — client-side recompute (SCOPE §2 row 7); currently a static shell. Would need the JS engine port validated against the golden fixture.

---

## Privacy

`research/wispr-transcript.md` contains real names and a private startup's commercial details.
**Local commits only — do not push to any public remote without redacting.**
