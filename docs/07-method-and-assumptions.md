# Method & Assumptions — and an Example Decision

## Why this section exists

This repo is a *transparent demo*: every number is hand-checkable arithmetic, not a black box. This note states the assumptions behind the model, and then works one **complete decision** end to end — because the story isn't finished until a decision is made.

---

## The worked decision: "Should we fund Assembly Line A?"

### Act 1 — The problem (computed, not asserted)

Under the Upside demand plan, **Assembly Line A** (the bottleneck) exceeds installed capacity in **four months**:

| Month | Load (hrs) | Installed (hrs) | Utilization | Overage (hrs) |
|---|---|---|---|---|
| Mar | 10,112 | 9,500 | 106.4% | 612 |
| **Apr** | **10,923** | 9,500 | **114.98%** | **1,423** |
| May | 10,319 | 9,500 | 108.6% | 819 |
| Dec | 9,719 | 9,500 | 102.3% | 219 |
| **Full year** | — | — | — | **3,073 hrs** |

### Act 2 — The cost of *not* funding it (computed)

Constrained ships 99.09% of the same uplifted demand. The shortfall is fully concentrated in **Dryers** (lowest-margin family). Full-year cost:

- **$531,728 lost contribution margin**
- **$1,251,441 lost revenue**

This is the exact figure the three-scenario identity proves: `upside value unlocked` = `margin at risk if not funded` = **$531,728**.

### Act 3 — The decision (this is the part that's usually missing)

Funding the bottleneck means adding **~3,073 hrs/yr** to Assembly Line A. The executive question: **is that worth $531,728 in annual margin?**

Two honest ways to fund it, with clearly-labelled assumptions:

**Option A — Overtime premium.** Suppose the extra hours cost a **50% labor premium**. If Assembly Line A's base labor is $60/hr, overtime costs $90/hr:
- Annual overtime cost = 3,073 hrs × $90 = **$276,570**
- Net annual gain = $531,728 − $276,570 = **$255,158**
- **Payback on the premium: the margin recovers the cost ~2× over the year. Fund it.**

**Option B — Machine lease / capex.** Suppose the capacity requires a **$450,000** annual lease:
- Net annual gain = $531,728 − $450,000 = **$81,728** (positive, but thin)
- **Payback: ~10 months. Marginal — funding it is defensible but not a slam dunk.**

**The takeaway is the structure, not the specific numbers.** The demo gives you *the exact cost of the constraint* ($531,728). The decision then becomes a *cost comparison* — margin recovered vs cost of capacity — instead of a hunch. **That is what S&OP/IBP is for: making the trade-off explicit before the capex meeting, not after.**

> **Honest caveat:** these cost figures are illustrative assumptions. The model computes the *margin side* ($531,728) exactly; the *cost side* (overtime premium, lease) is your input. The S4 Invest scenario (roadmap) would carry the capex/ROI into the model itself.

---

## Model assumptions (the honest limitations)

The repo is a point estimate, not a range, and each limitation is a named roadmap item:

| Assumption | What it means | Roadmap item |
|---|---|---|
| **Contribution margin, not gross** | `shipped × (price − variable cost)`; no fixed-overhead allocation | — |
| **No capex / ROI on invest** | `upside value unlocked` is revenue-side only | S4 Invest scenario |
| **No forecast error** | a single demand draw, not a range | MAPE cone / Monte Carlo |
| **No build-ahead / backorders** | unmet demand is a lost sale; no prebuilding to smooth Apr | build-ahead extension |
| **No inventory carrying cost** | inventory treated as free | turns / DIO / holding cost |
| **Margin-priority rationing** | highest-margin family first, no fairness floor | throughput-per-bottleneck-hour |

---

## Method (what's computed, what's assumed)

**Computed exactly by the engine:**
- Demand plan (base + upside uplift) — deterministic from seed `20260714`
- RCCP load vs installed capacity — every resource × month
- Constrained rationing — descending unit margin until hours exhausted
- Financials — revenue, contribution margin, lost revenue/margin, ending inventory

**Assumed (your inputs, clearly separable):**
- The upside uplift percentages per family
- The cost of capacity (overtime premium, lease) — *only* relevant to Act 3
- Hours-per-unit routing (in `families.json`)

Nothing is hardcoded in `kpi.py` — edit `datagen.py` and every number downstream changes (see [docs/01-architecture.md](01-architecture.md)).
