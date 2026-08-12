# HANDOFF — S&OP Cockpit Revamp (alignment done → build mockups)

**Date:** 2026-08-12 (supersedes the earlier version of this file from the same day).
**Repo:** `~/Documents/Aiwork/sop-integrated-planning` — branch `main`, remote `LaviSahu/sop-integrated-planning` (SSH).
**Why:** session hit ~130k context. The reading and alignment phase is **complete and durable in files**. The next
session builds mockups, which is where Lavi and the agent iterate visually.

---

## Read this first

**`SCOPE.md`** — the locked build scope. It is the contract for this revamp and it is current. Do not re-derive
any of it; it already contains the positioning, the 9 build decisions, the scenario matrix, the lever list, the
Stage-4 method, the visual direction, the research corrections (§8b), and the design rules from the transcript (§7).

Everything below is *only* what `SCOPE.md` does not already say.

---

## Status

| Phase | State |
|---|---|
| Grounded research (6 dimensions, 105 sources) | done — `research/findings.md`, `research/findings.html` |
| Transcript read + feedback extracted | **done** — folded into `SCOPE.md` §7 |
| All 6 screenshots read | **done** — folded into `SCOPE.md` §6b |
| Engine + spec digested | done — see "Engine facts" below |
| Scope locked | **done** — `SCOPE.md` |
| Mockups | **not started — this is the next job** |
| Implementation | not started. Do not start it. |

---

## What changed this session (corrections worth knowing)

Three things were wrong in earlier drafts because they came from subagent summaries rather than the sources.
All three are now fixed in `SCOPE.md`; they are listed here so the next session doesn't reintroduce them.

1. **The transcript is not an S&OP discussion.** It is the zerOm intro meeting (causal engine `axon.`, promotions
   demo on Union Coop data). Lavi is the EY consultant giving critical feedback — *his critique is the design brief.*
2. **The screenshots are not IBCS dashboards.** They are frames from a dark-canvas product deck
   ("KitchenOS / CMO Persona Walkthrough", slides 7, 9, 17, 19, 21 of 30). They are the reference for *visual
   quality and interaction patterns*, not chart grammar.
3. **Human-in-the-loop override was wrongly scoped out.** It is one of Lavi's recurring asks and appears in three
   of the six screenshots. Reopened in `SCOPE.md` §8, still needs Lavi's call on depth.

---

## Engine facts (from the codebase digest — saves you a re-read)

- 9 modules: `models`, `datagen`, `demand`, `capacity`, `constrain`, `finance`, `kpi`, `dashboard`, `cli`.
- Scenarios are a **hardcoded enum** (BASE/UPSIDE/CONSTRAINED) with parameters as literal tables in `datagen.py`.
  No config file, no CLI overrides, **no lever surface of any kind** exists today.
- `dashboard.build_context()` assembles JSON; `render_dashboard()` does a `__DATA_JSON__` string-replace into a
  single self-contained HTML file. Inline CSS, hand-rolled SVG, vanilla JS. **The renderer never recomputes anything.**
  Today's only interactivity is scenario tabs and a theme toggle.
- Regenerate: `PYTHONPATH=src python3 -m sop_integrated_planning.cli dashboard` → `output/dashboard.html`.

### The architecture fork that is still open

Client-side lever-drag recompute means **porting the planning math to JS**. Options considered: local compute
server (breaks the single self-contained file) and a precomputed lever grid (caps levers to a fixed grid) — both
rejected. **Recommendation, not yet confirmed by Lavi: port to JS, Python stays the reference implementation, and
a golden-fixture test asserts the JS reproduces Python's numbers for the 4 presets.**

`constrain.py`'s rationing loop is sequential and stateful (inventory carry + margin-priority order) — it is the
one piece where a naive JS port will silently differ. Fixture-cover it first.

---

## In flight when this handoff was written

One background agent was still running: a rewrite of **`mockups/tokens.css`** from light-primary to **dark-primary**
with IBCS notation tokens. **Verify the file before building on it** — check it is dark-primary and that the
notation tokens (actual solid / plan outline / forecast hatched, variance with ▲▼ glyphs, 4-step confidence line
weights) exist. If the rewrite didn't land, redo it against `SCOPE.md` §6b.

---

## Next job — mockups, one at a time, each approved before the next

Order is fixed in `SCOPE.md` §9: **layout shell → scenario comparison → levers/drill-down → KPI tiles → margin waterfall.**

Start with the **layout shell**. Constraints that bind it, all from `SCOPE.md`:
- Dark editorial canvas, IBCS notation inside charts, no glow, no gradients, no drop shadows.
- Small-multiples grid: rows = metrics, columns = scenarios, shared y-domain per metric-unit.
- Headline band up top (recommended scenario + binding-constraint callout, "5-second rule").
- Right-hand narrative rail. Cap 5–7 visible charts.
- Colour encodes **variance only** — scenario identity is fill pattern.
- Every text/background pair contrast-checked (Lavi caught an unreadable label live in the zerOm demo).

**Acceptance test for every number that ever appears:** it must be reproducible by hand in Excel (`SCOPE.md` §7).

### Two open questions for Lavi

1. **Planner override / HITL** — in scope, and how deep? (`SCOPE.md` §8)
2. **The JS-port fork** — confirm the golden-fixture approach above.

### Blocker on the Stage-4 goal

Stage 4 needs an explicit revenue/margin **target per scenario** plus a gap-to-plan line in $ and %.
`data/families.json` has **no targets**. That is new input data, not just a new chart. Raise it before claiming Stage 4.

---

## Suggested skills

- **`/brief`** — this session ran in brief mode; Lavi prefers it.
- **`dataviz`** — load **before** writing the first line of chart code. Non-optional for this work.
- **`artifact-design`** — layout/visual fundamentals for the mockups.
- Skip `code-review` / `simplify` until implementation actually lands.

---

## Working style (carry forward)

- **Judge files and diffs, never prose.** Two executors have reported success having changed zero files.
- **Read the sources yourself when they are the design input.** This session's three errors all came from trusting
  subagent summaries of the transcript and screenshots. Delegate breadth; read the things you are designing from.
- **Verify before claiming.** State it as verified only after running it; otherwise label `Assumption:`/`Unknown:`.
- Lavi is terse and decisive, pushes back on badly-scoped work, and wants to be grilled. Give a recommendation
  and one next action — not a survey of options.
- **Do not implement until he confirms.** He has said so explicitly, twice.

---

## Privacy

`research/wispr-transcript.md` contains real names and a private startup's commercial details.
**Local commits only — do not push to any public remote without redacting.**
