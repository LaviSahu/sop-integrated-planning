# Roadmap

This repo deliberately stops at a single-stage, monthly, three-scenario
model — enough to make the S&OP/IBP reconciliation argument concrete
and quantified, not a production planning system. Real enhancements
that were considered and consciously left out, in roughly the order
they'd add the most insight per unit of complexity:

## 1. Multi-period build-ahead

Today `constrain.py` caps `produced_units` at that month's own demand
(Deviation #4, `implementation-notes.md`) — the model never stockpiles
ahead of a seasonal peak it could in principle see coming, even though
the seasonality curves in `datagen.py` are known 12 months in advance.
A real planner facing April's Assembly-Line-A bottleneck would ask "can
we build Refrigerators early, in a slower month, and draw down
inventory in April instead of losing the sale?" Modeling that requires
a genuine multi-period optimizer (or at minimum a greedy look-ahead
heuristic) rather than the current month-by-month pass — a materially
bigger step than anything else on this list.

## 2. Demand uncertainty (Monte Carlo)

`datagen.py`'s ±3% jitter is a single deterministic draw per seed — one
"actual" outcome, not a distribution. A natural extension re-runs the
demand generator across many seeds (or samples a distribution directly
around the seasonal mean) and reports fill rate / lost margin as a
range or percentile band rather than a single point estimate — closer
to how demand planning literature (Wallace & Stahl's step 2) actually
treats a forecast: a range to plan against, not a promise.

## 3. Multiple resources binding at once

The current dataset was deliberately tuned (Deviation #2) to produce
exactly one clean bottleneck under Upside demand, because a single
unambiguous constraint is the clearest way to demonstrate the
mechanism. `constrain.py`'s rationing logic is already per-resource and
would run unmodified if two resources bound simultaneously — but the
dashboard's "the bottleneck" singular framing and `kpi.bottleneck_kpi`
(which picks one worst `(resource, month)`) would need to become a list
to represent that case honestly.

## 4. A real pre-S&OP reconciliation workflow

Right now the "decision" between Upside (invest) and Constrained (don't)
is two static scenarios computed once. A step toward an actual
reconciliation tool would let a user interactively dial a proposed
capacity investment (e.g. "what if we add 500 hours/month to Line A,
not the full gap") and see fill rate / lost margin move continuously
between the Constrained and Upside endpoints — turning the dashboard
from "here are three fixed outcomes" into "here is the trade-off curve,
pick a point on it."

## 5. Non-linear/tiered variable cost

`unit_variable_cost` is currently flat per family regardless of volume.
Real manufacturing cost curves often step (overtime premiums past a
capacity threshold, volume discounts on materials past a reorder
quantity) — modeling that would make the Constrained-vs-Upside margin
comparison even sharper, since overtime to hit Upside volumes isn't
actually free the way the current model implicitly assumes.

None of these are started. Each would be a genuine scope increase, not
a bug fix — flagged here rather than half-implemented, per the brief's
instruction to log real deviations rather than invent unrequested
policy.

Back to [Wiki Home](index.md).
