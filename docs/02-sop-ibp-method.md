# S&OP → IBP Method

## The monthly cycle (Wallace & Stahl)

Thomas Wallace and Robert Stahl's *Sales and Operations Planning: The
How-To Handbook* frames S&OP as a five-step monthly cycle that keeps
sales, operations, and finance working from one agreed number instead
of three competing spreadsheets:

1. **Data gathering** — close last month's actuals, refresh the
   baseline (`datagen.py`'s `data/families.json` / `data/resources.json`
   play this role here — a frozen, versioned starting point).
2. **Demand planning** — state what demand looks like, unconstrained,
   before anyone checks feasibility (`demand.py`).
3. **Supply planning** — check that demand against what can physically
   be produced; this repo's `capacity.py` (RCCP) and `constrain.py`
   (the constrained plan) are this step.
4. **Pre-S&OP reconciliation** — where a gap between demand and supply
   surfaces, someone has to decide what happens: invest in more
   capacity, or ration what's available. This repo encodes that
   decision as the UPSIDE vs CONSTRAINED scenario split (see
   `constrain.effective_capacity_hours`) rather than a meeting.
5. **Executive S&OP** — the monthly decision meeting where the
   reconciled plan gets approved. This repo's dashboard (`dashboard.py`)
   is built to be the artifact that meeting looks at.

## From S&OP to Integrated Business Planning

Oliver Wight's *The Transition from Sales and Operations Planning to
Integrated Business Planning* (2nd ed., 2022, ISBN 978-1604271911) and
Palmatier & Crum's *Enterprise Sales and Operations Planning* both
describe IBP's defining move as extending the same monthly
reconciliation to include the **financial plan** — not units and hours
alone, but revenue, margin, and inventory value, in the same cycle,
not a separate finance exercise weeks later. `finance.py` is that
extension in this repo: every `SupplyLine` (units) becomes a
`FinanceLine` (dollars) in the same monthly bucket, and `kpi.py`'s
catalog mixes operating KPIs (fill rate, utilization) with financial
ones (contribution margin, lost margin, upside value unlocked) in one
flat dict — deliberately not two separate reports.

## Rough-Cut Capacity Planning (RCCP)

RCCP is standard MRP-II/APICS body-of-knowledge practice (uncited, as
is standard for well-established operations-management terminology): a
feasibility test, not a detailed finite schedule. Before committing a
demand plan, load it against the key shared resources it would consume
and check whether *installed* capacity can support it. This repo's
`capacity.py` does exactly that — one number per (resource, month):
`utilization_pct = load_hours / resource.monthly_available_hours *
100`. It deliberately does not attempt detailed sequencing, setup
times, or shift patterns; that's the job of full Capacity Requirements
Planning downstream of S&OP, out of scope here.

## Margin-priority allocation

When a resource is genuinely over capacity (CONSTRAINED), someone has
to decide who gets the scarce hours. Rationing scarce capacity to the
highest-margin business first is a standard, uncited operations-
planning practice — the analogue of yield management in capacity-
constrained industries. `constrain.py`'s `_allowed_units_this_month`
implements it literally: sort the resource's users by descending
`unit_margin`, grant each family's full wanted hours in turn until the
budget runs out, and whatever's left over for the lowest-margin
families is whatever's left over — which, as the seeded Cascade
Appliances dataset shows, can be a real and sometimes severe shortfall
for the family sitting last in that queue.

## Why three scenarios, not one

A single demand-vs-capacity check answers "is the plan feasible."
Running BASE, UPSIDE, and CONSTRAINED side by side answers the
question an executive actually needs answered in the pre-S&OP
reconciliation step: *what is the upside worth, what does it cost to
capture it, and what does it cost if we don't?* See the
[Scenario Guide](05-scenario-guide.md) for the exact mechanics and the
real dollar figures the seeded dataset produces.

Next: [KPI Reference](03-kpi-reference.md).
