# SCOPE — S&OP Cockpit Revamp (locked 2026-08-12)

Supersedes the "stdlib-only / zero-dependency" positioning in `CLAUDE.md` and `README.md`.
`DESIGN.md` remains the behavioural contract; this file locks *what we are building* before it is amended.

---

## 1. Positioning

**From:** "zero-dependency white-box planning."
**To:** **"Fully transparent planning logic — no proprietary optimizer, every lever's effect is traceable arithmetic."**

Kinaxis / o9 / SAP IBP sell a black box: you change an input, a solver returns a number, and nobody can explain the number. This cockpit inverts that. Every figure on screen is reachable by hand from the inputs, and the UI can show that path on double-click. Transparency is the differentiator; the absence of a solver is what *makes* it possible, not a limitation we are apologising for.

## 2. Build decisions

| # | Decision | Locked |
|---|---|---|
| 1 | Data layer may use **pandas / numpy** | Yes — stdlib-only constraint dropped |
| 2 | Dashboard stays **hand-rolled HTML + inline SVG** | Yes — IBCS control lives here; no charting library |
| 3 | **No optimizer** — no LP/MIP/solver, no `scipy.optimize` | Yes, confirmed twice |
| 4 | Target **Gartner Stage 3 and Stage 4** | Yes — both, not "Stage 3 gesturing at 4" |
| 5 | Scenarios = **presets + build-your-own** | Yes (Lavi, 2026-08-12) |
| 6 | Stage-4 demand = **MAPE-driven residual cone** | Yes (Lavi, 2026-08-12) |
| 7 | Recompute runs **client-side in the browser** | Yes — a lever drag must not require a Python round-trip |
| 8 | Drill-down: **double-click any figure → its arithmetic** | Yes — the transparency claim, made literal |
| 9 | Single self-contained `output/dashboard.html` | Yes — no server, no CDN, no build step to view |

Full research rationale, the 105-source bibliography and the original ranked decisions: `research/findings.html`.

## 3. Scenario matrix

**Four anchor presets ship as buttons. Everything else is built from levers.** We do *not* render eight fixed
scenario panels — that was the sprawl risk. Presets are the guided tour; the lever panel is the sandbox.

| ID | Preset | Question it answers | What it changes vs BASE |
|---|---|---|---|
| S0 | **BASE** | What does the consensus plan look like? | nothing — the reference case |
| S1 | **CONSTRAINED** | What can we actually make? | capacity binds; TOC rationing by contribution margin |
| S2 | **UPSIDE** | What if demand lands high? | `upside_uplift_pct` per family (0–25%) applied |
| S3 | **INVEST** | Is relieving the bottleneck worth it? | added hours/shift on the binding resource, cost carried into P&L |

Rules:
- **Max 4 scenarios compared side-by-side**, always on a **shared axis scale** (IBCS: no rescaling between panels).
- A user-built scenario is a **named delta from BASE**, saved as a lever set — not a new code path.
- Every comparison shows **variance vs BASE**, not just levels.

## 4. Lever list

**Tier 1** is on the panel by default. **Tier 2** sits behind an "Advanced" disclosure — this is the anti-sprawl
mechanism: comprehensive underneath, calm on first render.

| Group | Tier 1 (visible) | Tier 2 (advanced) |
|---|---|---|
| **Demand** | volume multiplier (global), per-family uplift %, seasonality shift (±months) | forecast bias %, per-family MAPE override |
| **Supply** | available hours per resource (4 sliders), overtime hours | yield / scrap %, minimum lot size |
| **Policy** | safety stock (weeks of cover), rationing rule (**throughput-per-constraint** ▸ fair-share ▸ strategic-priority) | backorder vs lost sale (per family), build-ahead horizon (months) |
| **Financial** | unit price Δ%, unit variable cost Δ% | inventory carrying %, overtime premium %, stockout penalty per unit |
| **Inventory** | opening inventory Δ% | max inventory cap (units) |

Every lever is **traceable**: changing it must alter a named term in a formula we can display, or it does not ship.

## 5. Stage-4 layer — MAPE-driven residual cone

Not a solver, not a black box. Sampling and arithmetic:

1. **Backtest** the demand model over one fixed historical window → per-family residuals `actual − forecast`.
2. **MAPE** per family from those residuals; σ estimated from the residual distribution.
3. **Cone** = P10 / P50 / P90 fan projected forward, widening with horizon (σ scales with √h).
4. **Service level** and safety-stock adequacy read off the cone, not assumed.
5. Cone is **rendered as a band behind the plan line** — plan stays the hero, uncertainty is context.

Consequence worth stating: families with a *good* forecast get a narrow cone and less safety stock. That is the
insight the cockpit is for, and it falls out of the arithmetic rather than being asserted.

## 6. Data model (verified on disk)

- **6 families** — Refrigerators, Washers, Dryers, Microwaves, Dishwashers, +1. Each carries `unit_price`,
  `unit_variable_cost`, `unit_margin`, `opening_inventory_units`, `base_monthly_demand[12]`, `upside_uplift_pct`,
  `resource_hours_per_unit{}`.
- **4 resources** — Assembly Line A (9,500 h/mo), Assembly Line B (7,800), Test/QA (2,220), Packaging (1,600).
- **12 monthly buckets.**
- Keeping 6 well-characterised families rather than inflating to 12 thin ones: demo clarity beats fake breadth.

## 6b. Visual direction (locked 2026-08-12)

**Dark editorial canvas + IBCS notation discipline inside the charts.** These are not in conflict: the shell is
editorial, the chart grammar is rigorous.

- **Shell:** near-black canvas, panels lifted one step with hairline borders, uppercase tracked micro-labels,
  a right-hand narrative rail. Taken from the reference deck.
- **Charts:** IBCS notation — actual solid, plan outline, forecast hatched, shared scales across compared
  scenarios, variance as hue **plus** ▲/▼ glyph (never hue alone).
- **Dropped from the references:** neon glow, decorative multi-hue palettes, Sankey/node-link diagrams. Allowed
  hues are one brand accent plus semantic good/bad/warn/info; everything else is neutral ink.
- **Confidence encoding** — line weight in 4 steps, dashed for low — is lifted from the deck and reused for the
  P10/P50/P90 forecast cone.

Tokens: `mockups/tokens.css`.

### Patterns taken from the reference deck

| Pattern | Source slide | Use here |
|---|---|---|
| **"Click any number, see how it was made"** — 5-step provenance modal | 7/30 | Demand → Capacity → Rationing → Supply → Financials → KPI, each showing real arithmetic. **The centrepiece.** |
| Three lenses on one canvas, zero navigation | 17/30 | Plan / Explain / Simulate as modes, not pages |
| KPI health rail with status dots, green as well as red | 17/30 | MECE KPI set; positives surfaced |
| Confidence as line weight, dashed = low | 21/30 | MAPE cone |

**Deliberately NOT copied** — this cockpit has no LLM and no causal engine, so agent-consensus panels, causal
graphs and token-cost breakdowns would be theatre. Every pattern we take must be backed by arithmetic we actually run.

## 7. Design rules (from Lavi's critique of zerOm in the transcript)

Source note: the transcript is the **zerOm intro meeting** — their causal engine `axon.` plus a promotions demo on
Union Coop data. It is not an S&OP discussion. Lavi is the EY supply-chain consultant giving critical feedback,
and **that critique is the design brief.** The reference screenshots are separately from a "KitchenOS / CMO Persona
Walkthrough" product deck. Full transcript read complete; timestamps below are traceable in
`research/wispr-transcript.md`.

### The governing requirement

> **"I should be able to do it on Excel and the same thing should come out as output."** [56:33]

**Read this for the idea, not the word.** "Excel" is Lavi's shorthand for *hand-checkable arithmetic* — it is not
a requirement to export to Excel, to restrict the math to spreadsheet functions, or to build any spreadsheet
feature. The bar is: **every number on screen must be re-derivable by a human from inputs visible on screen**,
with the operation shown. If a figure can't be traced back that way, it doesn't belong on screen.

**Applies to the whole transcript:** it is directional input on intent, captured live in a critique of someone
else's product. Take the underlying principle from each quote; do not turn incidental wording into a spec item.

And the line that validates the entire project [84:07]:

> **S&OP planning runs on exactly this — whether you are able to just explain.**

Lavi's diagnosis of why transaction systems (SAP) outsell planning systems: transaction systems have
transparency, planning systems don't [57:47]. This cockpit is the argument that a planning system can have it too.

### Rules

1. **MECE KPIs** — no two tiles measure the same thing. Flag when "needs attention" metrics share drivers [42:00].
2. **Surface positives alongside pain** — a cockpit that only shows failure gets ignored.
3. **Full explainability** — every number drills to its arithmetic. Trust comes from **repeatable, consistent
   behaviour**, not sophistication [55:04]. "If you can explain, there is no problem" [55:38].
4. **Traceable, not memorised** — nobody needs to know the formulas by heart; an analytical user must be able to
   trace and tweak and get the same trail [59:37].
5. **Backtesting is visible**, not a footnote — one fixed historical window re-run against actuals.
6. **Cover the edge cases** — "don't give a happy flow" [50:53]. Zero demand, capacity 0, negative margin,
   stockout, 100% utilisation: they must render, not crash.
7. **No role-locked views** — a view tuned for one persona must not suppress signals its peers need [43:32].
8. **Ambiguous status gets disputed** — "needs attention" must be unquestionable or it derails every demo [43:49].
9. **Diagnosis → recommendation must land smoothly**, and be *solid* before it prescribes. Don't broadly assign
   blame [70:59, 72:15].
10. **Non-negotiable business rules must be hardcodable** by the user, so the system can't re-derive a wrong
    assumption [86:02]. → this is the planner-override item reopened in §8.
11. **Be careful with assumptions** [84:14] — state them on screen, don't bury them.
12. **Contrast is a correctness issue.** He caught unreadable text live in the demo [45:59]. On a dark canvas,
    verify every text/background pair.
13. **Complex structures collapse to a table**, with full complexity on drill-down [62:24]. Tabular alongside
    visual, always.

## 8. Explicitly out of scope

- Any LP/MIP/heuristic **optimizer**.
- Multi-site / multi-echelon network. Single plant, single DC.
- Live ERP integration. JSON in, HTML out.

**Reopened 2026-08-12 — planner override / human-in-the-loop.** An earlier draft of this file excluded it as
"belongs to the zerOm thread." That was wrong: it is one of Lavi's recurring asks in the transcript (feed
corrections back to override the system's assumptions) and it appears in three of the six reference screenshots.
For this cockpit it means: a planner can override a computed figure, the override is visibly flagged as an
override, and the delta versus the computed value stays on screen. Scope to be confirmed before implementation.

## 8b. Research alignment (`research/findings.md` — 6 dimensions, 105 sources)

Corrections the research forces on the draft above. **These override anything earlier in this file.**

### Must fix in the engine (real bugs, not preferences)

1. **Rationing sorts by the wrong key.** Current code sorts by raw `unit_margin`. Theory of Constraints says
   sort by **contribution per bottleneck-hour** (`unit_margin ÷ hours_on_binding_resource`). This is the classic
   Goldratt error and a practitioner spots it immediately.
2. **`gross_margin` is mislabelled.** It computes `shipped × unit_margin` — that is **contribution margin**.
   Rename everywhere. Do *not* add a true gross margin; that reintroduces the arbitrary overhead allocation the
   whole approach exists to avoid.
3. **Keep exactly ONE binding resource.** This is what makes the no-optimizer position rigorous rather than
   convenient: with a single constraint, the TOC greedy heuristic **provably equals the LP optimum**. Adding a
   second bottleneck reopens the optimizer question. Resist it.

### Chart grammar — prescribed, not stylistic

| Panel | Chart type |
|---|---|
| Utilization, fill rate (KPI vs target) | **bullet graph** |
| Margin bridge | **vertical waterfall** — base → +upside lift → −constrained penalty → realized |
| Structural scenario comparison | **horizontal bars** (vertical columns reserved for time series) |
| Bottleneck load | **graded bands** safe / strained / critical — not a binary >100% flag |

**Kill list:** pies and donuts, gauges and speedometers, 3D, dual y-axis, gradient fills, drop shadows, heavy gridlines.

**Shared y-domain per metric-unit, computed once across all scenarios and applied to every panel.** No panel
auto-scales independently. The research names this as the fix for the repo's stated top pain.

**Layout:** true small multiples — rows = metrics (utilization, fill rate, margin, unmet demand), columns = scenarios.
Top headline band carries a recommended-scenario callout and the binding-constraint headline (the "5-second rule").
Cap visible charts at **5–7**, ordered by decision importance.

⚠️ **Colour is reserved for variance from BASE.** Scenario identity is carried by **fill pattern** (solid / hollow /
hatched), not by a colour per scenario. The current dashboard uses a solid colour per scenario — that is a direct
IBCS violation and must change.

### Stage gates — what must be visibly true on screen

**Stage 3:** forecast series distinct from actuals · P10/P50/P90 cone rendered · MAPE **and bias** as KPI tiles ·
consensus-demand reconciliation shown as an explicit *step*, not just a number · scenarios compared over a horizon.

**Stage 4:** an explicit revenue/margin **target input per scenario**, plus a **gap-to-plan line in $ and %**.
The research calls this "the integrated reconciliation step that defines IBP over classic S&OP."

> **Data-model gap:** `families.json` carries no targets. Stage 4 cannot be claimed until a target input exists.
> This is new input data, not just a new chart.

### KPI gaps vs `docs/03-kpi-reference.md`

Missing today: MAPE, forecast bias, inventory turns / days-of-cover, backorder-backlog value, service level
(distinct from fill rate), schedule attainment, gap-to-plan, and payback/ROI for the invest case.
**Do not add all of them** — the research warns of clutter. Gate them; turns + OEE is the suggested minimal set.

### Known tensions — flagged, not resolved

- **Dark-theme IBCS is unresourced territory.** IBCS's canonical example is solid black on white, and the standard
  gives no dark-mode guidance. Solid/hollow/hatched notation on a dark canvas is ours to invent. Not a violation —
  IBCS does not mandate a light background — but there is no source to lean on. Own the adaptation deliberately.
- **Client-side recompute exceeds what the research envisions.** `findings.md` assumes compute happens once in
  Python and renders to static SVG; it describes one illustrative re-plan panel, not a live engine. The
  auditability argument ("a reviewer can read the Python arithmetic") must be extended to hand-rolled JS.
  This is why the golden-fixture test is non-negotiable, not a nicety.
- **Research recommended Stage 3 + gesture at Stage 4.** Lavi's pivot targets both fully. Accepted override,
  recorded here so it is a choice rather than a drift.
- **Research recommended exactly 3 scenarios.** We ship 4 — INVEST is backed by pillar 12 (fund-the-bottleneck
  with payback/ROI), so the addition is supported, but scenario count is now at the researched ceiling. No more.

## 9. Build order (mockups first, one at a time, each approved before the next)

1. Layout shell
2. Scenario comparison
3. Levers + drill-down interaction
4. KPI tiles
5. Margin waterfall

No engine refactor until the mockups are signed off.
