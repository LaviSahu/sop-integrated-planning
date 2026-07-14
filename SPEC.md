# S&OP Integrated Planning — Build Spec (frozen)

Showcase-grade, self-contained S&OP / IBP decision cockpit. Pure Python 3.10+ **stdlib only** (no pip installs needed to run the demo). Original work — NO references to EY, clients, or any consulting firm anywhere in code or docs.

## What it is

An end-to-end monthly S&OP → IBP reconciliation engine for a synthetic
appliance manufacturer, "Cascade Appliances": generate a seeded synthetic
demand/capacity dataset → build an unconstrained demand plan → run
Rough-Cut Capacity Planning (RCCP) against installed capacity → produce a
constrained supply plan (margin-priority rationing when capacity is
short) → reconcile the result into a financial summary → render a
self-contained HTML dashboard comparing three scenarios side by side.

## Repo layout

```
sop-integrated-planning/
├── README.md                      # showcase README
├── LICENSE                        # MIT, copyright Lavi Sahu
├── pyproject.toml                 # metadata only, no deps
├── Makefile                       # demo / test / dashboard / clean targets
├── SPEC.md                        # this file
├── DESIGN.md                      # frozen dashboard design spec
├── implementation-notes.md        # build log, deviations
├── data/
│   ├── families.json              # 6 synthetic product families
│   └── resources.json             # 4 synthetic shared production resources
├── src/sop_integrated_planning/
│   ├── __init__.py  __main__.py  cli.py
│   ├── models.py     # dataclasses: Family, Resource, DemandLine, ResourceLoad,
│   │                 #   SupplyLine, FinanceLine, FinanceSummary, Kpi; ScenarioId enum
│   ├── datagen.py    # seeded synthetic dataset generator
│   ├── demand.py     # unconstrained demand plan (base, optionally uplifted)
│   ├── capacity.py   # Rough-Cut Capacity Planning (RCCP)
│   ├── constrain.py  # constrained supply plan: margin-priority rationing
│   ├── finance.py    # financial reconciliation (revenue, margin, lost margin)
│   ├── kpi.py        # KPI catalog computed from real engine outputs
│   └── dashboard.py  # self-contained HTML dashboard generator (inline CSS/JS/SVG)
├── tests/            # stdlib unittest, runnable via `python -m unittest discover`
├── docs/             # wiki-style pages
└── output/           # gitignored except .gitkeep; comparison.json + dashboard.html land here
```

## Domain spec

### The three scenarios (`models.ScenarioId`)

- **BASE** — base demand against installed (base) capacity. Feasible by
  construction: the "we already agreed to this" monthly plan (Wallace &
  Stahl's S&OP cycle).
- **UPSIDE** — base demand + a per-family promotion/market-growth uplift,
  **with** the capacity gap RCCP exposes closed by an assumed investment
  ("if we add capacity"). Every family ships 100% of demand.
- **CONSTRAINED** — the identical uplifted demand, but capacity held at
  installed/base level (no investment) — "if we don't." `constrain.py`
  rations scarce hours by descending unit margin, and the resulting
  fill-rate shortfall and lost margin are real, computed consequences,
  not asserted numbers.

RCCP utilization (`capacity.py`) is **always** measured against each
resource's installed capacity, regardless of scenario — that is what
makes UPSIDE's bottleneck diagnostically visible even though UPSIDE's
supply plan fully ships. Only `constrain.py` decides whether the gap
gets invested away (UPSIDE) or rationed (CONSTRAINED).

### datagen.py — synthetic dataset ("Cascade Appliances", invented)

- 6 product families (Refrigerators, Washers, Dryers, Microwaves,
  Dishwashers, Ranges): price, variable cost, opening inventory, average
  monthly demand, per-family upside uplift %, resource-hours-per-unit.
- 4 shared production resources (Assembly Line A/B, Test/QA, Packaging),
  each with fixed installed monthly hours.
- Family-specific seasonal shape (spring remodel bump, Q4 holiday bump),
  normalized to average 1.0 so the annual total matches the stated
  average exactly; seeded ±3% monthly jitter.
- `SEED = 20260714`. Same seed → byte-identical `data/*.json`.
- **Modeling requirement**: the resource-hour intensities, seasonal
  curves, and per-family uplift percentages must multiply out so BASE
  stays ≤100% utilization on every resource/month, while UPSIDE
  genuinely exceeds 100% on at least one resource, purely as an emergent
  consequence of the data — never hardcoded. See
  `implementation-notes.md` for the tuning pass that got there.

### demand.py

`monthly_demand(family, month, scenario)`: base value, or base ×
`(1 + upside_uplift_pct)` for UPSIDE/CONSTRAINED (which share one demand
plan).

### capacity.py — Rough-Cut Capacity Planning

Standard MRP-II/APICS feasibility check (uncited, standard practice):
sum demand × hours-per-unit across every family sharing a resource, per
month; utilization = load / installed hours; `is_bottleneck` = strictly
over 100%.

### constrain.py

`effective_capacity_hours(scenario, resource, load_hours)`: BASE/
CONSTRAINED return installed hours unchanged; UPSIDE tops up to exactly
match load whenever load would otherwise exceed it. When a resource is
still over capacity (CONSTRAINED), hours are rationed by **descending
unit margin** — a standard, uncited operations-planning priority rule —
greedily, family by family. A family's actual output is capped by the
most-binding resource it touches. No backorders: `shipped = min(opening
+ produced, demand)`; unmet demand this month is a lost sale, not a
promise for next month.

### finance.py

Revenue/margin from **shipped** units (what was actually sold); lost
revenue/margin from **unmet** units (the value of demand the supply plan
couldn't produce — always zero in BASE/UPSIDE by construction, real in
CONSTRAINED). Ending inventory value = December's closing balance only,
at variable cost (not summed across months, or carried stock would be
double-counted).

### kpi.py — catalog, each computed (not hardcoded)

Fill rate per scenario, bottleneck resource/month/utilization, revenue &
gross margin per scenario, lost revenue/margin at risk (CONSTRAINED),
upside value unlocked (Δ gross margin, UPSIDE − CONSTRAINED), ending
inventory value per scenario.

### dashboard.py

ONE self-contained `output/dashboard.html`: dual light/dark theme,
inline CSS + vanilla JS + inline SVG charts (no CDN). Sections: KPI tile
row (fill rate ×3, bottleneck utilization, upside value unlocked, margin
at risk), capacity-utilization bar chart per resource with a 100% line
(scenario tabs), demand-vs-supply monthly gap chart (scenario tabs),
financial reconciliation table by family (scenario tabs), a computed
exec-takeaway callout. Data embedded as JSON in a `<script>` tag via the
`__DATA_JSON__` sentinel + `</` → `<\/` escape technique (not
`str.format`, so literal `{ }` in CSS/JS stay intact).

### cli.py

```
python -m sop_integrated_planning plan base|upside|constrained   # one scenario, console + optional JSON
python -m sop_integrated_planning compare                        # all three scenarios side by side
python -m sop_integrated_planning demo                            # (re)generate data, run all scenarios, render dashboard
python -m sop_integrated_planning dashboard                       # rebuild dashboard.html from current data
```

Console output: hand-rolled fixed-width tables, ANSI highlighting for
over-capacity resources (isatty-gated).

### tests/ — unittest

Real math and boundary asserts per module (including an exact
100%-utilization boundary that must NOT trip `is_bottleneck`), a
full-pipeline integration test on the real seeded dataset (asserting
BASE ≤100%, UPSIDE >100% somewhere, CONSTRAINED fill <100% and lost
margin >0), and a dashboard-renders test (self-contained, JSON-safe
against embedded `</script>` strings).

## Style

Type hints everywhere (`from __future__ import annotations`),
dataclasses, no globals; functions over classes outside `models.py`;
each module has a prose docstring explaining the S&OP/IBP concept for a
reader learning the domain. Deviations from this spec: logged in
`implementation-notes.md` under "Deviations", conservative option
chosen, kept going.

## Citations (hard guardrail — do not add, invent, or alter)

- Wallace, Thomas F., and Robert A. Stahl. *Sales and Operations
  Planning: The How-To Handbook.*
- Oliver Wight. *The Transition from Sales and Operations Planning to
  Integrated Business Planning.* 2nd ed. 2022. ISBN 978-1604271911.
- Palmatier, George E., and Colleen Crum. *Enterprise Sales and
  Operations Planning.*
- Rough-Cut Capacity Planning (RCCP) is standard MRP-II/APICS
  body-of-knowledge practice — used uncited, as is standard for
  well-established operations-management terminology.
