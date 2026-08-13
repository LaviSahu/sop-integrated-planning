# The 3,073-Hour Decision — What the Bottleneck Is Worth

One number turns a capacity debate into a capex decision:
**$531,728** — the contribution margin on the table, this year, at this
seasonality, if Assembly Line A is not funded. This is the story of how
that number is found, and the Invest scenario that turns it into a
decision.

This is the decision arc of the S&OP cockpit, told as a story. The
working arithmetic — every row, every assumption, both funding options —
lives in [07-method-and-assumptions.md](07-method-and-assumptions.md);
this page is what an executive should actually read. The identity that
ties the two scenarios together is proven in
[05-scenario-guide.md](05-scenario-guide.md).

---

## Act 1 — The signal: April is where the plan breaks

The Upside demand plan is the "if we say yes to demand" forecast. It is
also, for four months of the year, a plan Assembly Line A physically
cannot execute — and **April is the month the plan breaks**.

| Month | Load (hrs) | Installed (hrs) | Utilization | Overage (hrs) |
|---|---|---|---|---|
| Mar | 10,112 | 9,500 | 106.4% | 612 |
| **Apr** | **10,923** | 9,500 | **114.98%** | **1,423** |
| May | 10,319 | 9,500 | 108.6% | 819 |
| Dec | 9,719 | 9,500 | 102.3% | 219 |
| **Full year** | — | — | — | **3,073 hrs** |

The constraint is **Assembly Line A (`RES-LINEA`)**, the plant's single
bottleneck at 9,500 hrs/month installed. Seasonality is the driver:
demand peaks in April and May, and RCCP — Rough-Cut Capacity Planning —
exists precisely to surface this *before* the plant lives it. A 114.98%
reading is not a forecasting problem. It is a statement that a
15-point capacity gap will be resolved one way or another — by planning,
or by firefighting in the plant. The signal is not "we might be tight."
The signal is "1,423 hours of April demand have nowhere to go."

---

## Act 2 — The cost of doing nothing: $531,728 of margin, all of it in Dryers

Do nothing, and the plant ships 99.09% of that uplifted demand — not
100%, and the shortfall is not spread evenly. It is concentrated exactly
where the numbers say it will be.

- **$1,251,441 lost revenue**
- **$531,728 lost contribution margin**
- **100% of the shortfall lands in one family: Dryers (`FAM-DRY`)** — the
  lowest-margin family on the bottleneck resource, and therefore the
  last the rationing logic protects. Refrigerators and Washers ship
  100% every month of the year. Dryers alone pays the price of the
  un-funded upside.

This is why the number is *contribution margin* — price minus variable
cost, the money that actually survives to cover the plant — not revenue.
Revenue is headline; margin is the check that clears. The identity that
makes this bulletproof:

```
upside_value_unlocked = margin at risk if not funded = $531,728
```

Upside and Constrained run the *same* uplifted demand. The only
difference is whether the capacity gap gets funded. Every dollar of
margin Constrained fails to capture is a dollar Upside captured by
paying for the missing hours. One number, proven two ways.

**Why this belongs in a pre-S&OP meeting:** most capacity debates arrive
as a utilization chart and a plea. This arrives as a price tag on the
bottleneck — "$531,728 of contribution margin is sitting on Assembly
Line A, and it only moves if someone with a capex budget moves it." That
is not an operations problem. That is a P&L decision, made with the
company's own numbers, before the capex meeting — not after it.

---

## Act 3 — The decision: turning the number into an action

The dashboard's fourth preset — **S4, Invest** — exists to ask exactly
one question, printed on the button itself:

> **"Is relieving the bottleneck worth it?"**

That is the decision. And the whole point of the previous two acts is
that the decision now has a shape. The bottleneck is worth **3,073
hours** — the full-year overage on Assembly Line A. The margin those
hours carry is **$531,728**. So the executive question stops being "do
we have a bottleneck?" and becomes a *cost comparison*:

- **What does 3,073 hours of capacity cost?**
- **Does the $531,728 of recovered margin cover it?**
- **How fast does the payback land, and what happens if demand or the
  cost moves?**

The S4 Invest scenario is how the model answers that for real — the
scenario that turns the number into a decision. The honest sketch of how
it should be built:

- **Carry the capex into the P&L.** The investment appears as a real
  cost line in the scenario's financials — not a footnote — matched
  against the exact margin it recovers. Same ledger, both sides.
- **Compute payback and ROI.** Margin recovered ÷ cost of capacity, on
  the 3,073 hours that actually bind.
- **Run the sensitivity.** What if the uplift lands **lower** than Upside
  (fewer hours needed, less to recover)? What if it lands **higher**
  (more hours, more margin at risk)? What if the capacity costs more, or
  less, than the working assumption? The decision should survive the
  number changing — or fail loudly in the direction we can see.
- **Dial the hours, not just buy all-or-nothing.** The full gap may not
  be the right purchase — a partial add (e.g. 500 hrs/month, not the
  whole 3,073) is the real-world trade, and it should be visible as a
  continuous move between Constrained and Upside, not a binary.

---

## What the Invest scenario WILL compute (the honest spec)

The above is the **planned build**, not the current model. To keep the
demo honest, exactly what S4 will compute and what it will assume:

**Computed by the engine:**
- **Capacity cost carried into the P&L** — the investment as an explicit
  cost line against the scenario's contribution margin.
- **Payback / ROI** — margin recovered from the relieved hours vs the
  cost of that capacity, on the 3,073-hour gap.
- **Margin recovered vs cost** — the direct comparison that decides it:
  recovered > cost is fund; recovered < cost is don't.
- **Sensitivity on both axes** — demand uplift (+/−) and cost (+/−),
  so the verdict is a band, not a single fragile point.

**Assumed (your inputs, clearly separable):**
- The cost of the capacity — lease, purchase, overtime premium, whatever
  the company actually faces. The margin side is computed exactly; the
  cost side is the planner's input. The worked example in
  [07-method-and-assumptions.md](07-method-and-assumptions.md) shows
  both honest ends: a $276,570 overtime premium nets $255,158; a
  $450,000 lease nets $81,728. The story is the same either way — margin
  recovered against cost of capacity — only the verdict's margin changes.

**Status: not in the engine.** The S4 Invest preset already sits in the
dashboard, disabled and tagged *"not in engine"* — the roadmap's honest
marker that this scenario is the next build, not a claim. When it ships,
the payback/ROI it returns will be the demo's Act 3, computed instead of
narrated.

---

## The closing line

**The cost of NOT investing is a computed number — $531,728 — and the
value of investing is the same number. The decision is whether the
capacity is worth that price.**

Everything else — the utilization chart, the firefighting, the debate —
is downstream of that one question. The cockpit's job is to make sure
the question gets asked in a meeting with a capex budget, with the
company's own arithmetic on the table, instead of in the plant in April.

Next: [Method & Assumptions](07-method-and-assumptions.md) — the working
numbers behind this story. Back to [Wiki Home](index.md).
