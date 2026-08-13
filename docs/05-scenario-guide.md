# Scenario Guide

Three scenarios, one demand-vs-capacity tension, run side by side so an
executive can see what the upside is worth, what it costs to capture,
and what it costs to walk away from. All three run against the exact
same seeded Cascade Appliances dataset (`data/families.json` /
`data/resources.json`) — nothing about the input data changes between
scenarios; only the demand overlay and the capacity-investment
assumption do.

## Base

**Assumption**: `base_monthly_demand` only, no uplift. Installed
capacity (`monthly_available_hours`), no investment.

**What it represents**: the plan already agreed to — S&OP's "we already
committed to this" baseline (Wallace & Stahl step 3, supply planning,
confirms this is feasible before anyone asks "what if").

**Real numbers**: 100.00% fill rate every month, every family. Peak
resource utilization 94.48% (Assembly Line A) — feasible with headroom,
by construction. $127,687,935 revenue, $52,203,890 contribution margin,
$8,421,000 December ending inventory.

## Upside

**Assumption**: `base_monthly_demand * (1 + upside_uplift_pct)` for
every family with a nonzero uplift (Refrigerators, Washers, Dryers;
Microwaves and Ranges are unaffected — `upside_uplift_pct = 0.0`).
RCCP utilization is still measured against installed capacity — this is
what genuinely exposes the bottleneck rather than hiding it — but
`constrain.effective_capacity_hours` assumes the business closes
exactly the gap RCCP flags, i.e. invests in the capacity the uplift
requires. Supply is therefore never rationed in this scenario.

**What it represents**: "if we say yes to the upside and fund the
capacity it needs" — the value on the table, and the RCCP evidence for
why a capacity conversation is needed at all.

**Real numbers**: 100.00% fill rate (full investment assumption).
Assembly Line A peaks at **114.98%** utilization in **April** against
its 9,500 hrs/month installed capacity — the sole bottleneck; the
next-closest resource, Test/QA, peaks at 95.34%, safely under 100%. This
>100% reading is the emergent proof the brief requires: nothing in
`kpi.py` or `capacity.py` asserts a bottleneck exists, it falls out of
seasonality × uplift × hours-per-unit arithmetic. $148,472,953 revenue,
$60,625,548 contribution margin — $8,421,000 December ending inventory
(unchanged from Base: the model doesn't build ahead in either
direction, see Deviation #4 in `implementation-notes.md`).

## Constrained

**Assumption**: identical uplifted demand to Upside. Capacity held at
the *same* installed level as Base — no investment. Where a resource's
monthly load exceeds installed hours, `constrain.py` rations available
hours to each family in strict descending `unit_margin` order
(Refrigerators $537 > Washers $328 > Dryers $297 on the bottleneck
resource) until the budget is exhausted.

**What it represents**: "if we say yes to the upside but don't fund the
capacity" — the real, quantified cost of chasing the upside without
paying for the resource it needs.

**Real numbers**: 99.09% fill rate overall — Refrigerators and Washers
stay fully protected (100% fill, every month, all year); Dryers absorbs
the entire shortfall, worst in May at 57.95% fill that month. Full-year
result: $1,251,441 lost revenue, **$531,728 lost margin**, concentrated
entirely in Dryers (`FAM-DRY`). December ending inventory drops to
$7,375,800 (vs. $8,421,000 in Base/Upside) — the rationed family simply
never builds the inventory it would have in an unconstrained world.

## The identity that ties Upside and Constrained together

```
upside_value_unlocked = upside.total_gross_margin - constrained.total_gross_margin
                       = $60,625,548 - $60,093,820
                       = $531,728
```

This is exactly equal to Constrained's lost margin, by construction —
not a coincidence, and not two separate models that happen to agree.
Upside and Constrained ship against the *same* uplifted demand; the
only difference is whether the capacity gap RCCP identified gets funded.
Every unit of contribution margin Constrained fails to capture is, definitionally,
margin Upside *did* capture by paying for the missing hours. This is the
one number that turns "we have a bottleneck" into "here is what the
bottleneck is worth in dollars, this year, at this seasonality" — the
number a pre-S&OP reconciliation meeting exists to put in front of
someone with a capex budget.

Next: [Roadmap](06-roadmap.md).
