# S&OP Cockpit Revamp — Grounded Research Findings

_Generated 2026-08-12. 6 dimensions, 7 agents, 0 errors, ~634k tokens. Every claim cited to a free academic library (arXiv, Semantic Scholar, SSRN, Google Scholar) or authoritative practitioner source (APICS/ASCM, Gartner, IBCS). Interactive version: `findings.html`._

## Executive summary

The six dimensions converge on ONE identity for this repo: a WHITE-BOX, fully-auditable S&OP/IBP cockpit, explicitly contrasted with the black-box LP/ML optimizers (Kinaxis, o9, SAP IBP, Blue Yonder, OMP) that own the Gartner MQ. That identity resolves the central tension in the findings: every dimension that pushed for "more realism" (methodology, data, financials) ALSO warned that crossing into LP/probabilistic optimization turns a portfolio piece into a toy reimplementation. The repo already has the right bones — a genuine 12-month rolling inventory carry (constrain.py:143, opening←ending), RCCP at family granularity (doctrinally correct per Vollmann), finance integration in one cycle (the IBP definer), and a single TOC bottleneck. But it hard-codes three simplifications the literature treats as core PLANNING levers, not optional: deterministic demand (no forecast error, MAPE, or consensus step — the engine of the whole cycle), lost-sale-only (no backorders — unrealistic for durable goods), and a hard cap forbidding build-ahead (no level/chase strategy, leaving seasonality un-addressable). It also carries one outright correctness bug (rationing by per-unit margin instead of contribution per bottleneck-hour — the classic Goldratt error), one mislabel bug (the field called "gross margin" is mathematically contribution margin, models.py:101), and one misleading display (a binary >100% bottleneck flag that ignores the nonlinear congestion of Kingman's VUT equation, where 97% utilization is qualitatively worse than 90%). The factual premise in the original prompt is wrong: this is NOT a single-period repo — it is a 12-month plan with month-to-month inventory carry; the real gaps are no rolling RE-PLAN, no demand uncertainty, no backorders, no build-ahead, and no consensus/exec tiers. The revamp's job is to reach defensible Stage-3 maturity (consensus demand + forecast error/MAPE + scenarios + financial reconciliation) using ONLY auditable, eyeball-verifiable mechanisms — and to position that honestly against the market rather than fake being an optimizer.

## Revamp pillars

**1.** 1. WHITE-BOX POSITIONING (README/docs): name the Gartner MQ leaders (Kinaxis, o9, SAP IBP, Blue Yonder, OMP) and state the axis of differentiation — zero-install stdlib reproducibility + fully auditable arithmetic vs their black-box LP/ML solvers. Label the engine precisely as 'greedy TOC heuristic, exact when one resource binds' everywhere it is described. Turn RCCP's 'feasible-not-optimal' practitioner critique into the sourced design rationale for transparency, not a weakness to hide.
**2.** 2. TOC RATIONING FIX (constrain.py:86): change the sort key from f.unit_margin to f.unit_margin / f.resource_hours_per_unit[resource.id] — contribution per bottleneck-hour on THIS resource. Keep exactly ONE binding constraint in the dataset so the greedy heuristic provably equals the LP optimum and the demo output stays stable; document the exactness boundary in implementation-notes.md. Rank separately per resource since the binding resource can differ across families.
**3.** 3. CONTRIBUTION-MARGIN RENAME (models.py, finance.py, kpi.py, dashboard.py, docs): unit_margin / gross_margin -> contribution_margin everywhere. The math is already correct (price - variable_cost); only the name lies. Do NOT introduce true gross margin with allocated fixed overhead.
**4.** 4. FORECAST/ACTUAL SPLIT (datagen.py + kpi.py + dashboard.py): generate two correlated series per family — a forecast (what sales committed) and an actual (the truth) — with seeded Normal noise at a 15-30% MAPE target and a configurable per-family bias term. Render a P10/P50/P90 cone around the forecast. Add forecast_accuracy (MAPE), forecast_bias, and a consensus-demand reconciliation step (marketing override merged with statistical baseline) to kpi.py. Matches the M5-competition probabilistic-forecasting standard at zero solver cost.
**5.** 5. ROLLING-BALANCE SURFACING + RE-PLAN PANEL (dashboard.py + kpi.py): the engine ALREADY rolls Opening->Ending each month (constrain.py:143) — surface it as a days-of-cover KPI (ending inventory / avg daily demand) and an inventory-position-over-time chart. Add ONE illustrative 'frozen actual / rolling plan' panel: simulate 2-3 months of actuals diverging from forecast, re-run the plan from the current month forward, show how the constrained recommendation shifts. This makes the 'monthly cycle' visible rather than asserted, without full multi-pass machinery.
**6.** 6. PER-FAMILY STOCKOUT POLICY (families.json + constrain.py): add a stockout_policy field (backorder|lost_sale). When backorder, carry unmet units into next month's demand (opening[family.id] = ending still holds, but unmet propagates as a backlog). Add a backorder_value/backlog KPI. Default durable families (refrigerators, ranges) to backorder, impulse families (microwaves) to lost-sale — itself a defensible planning narrative.
**7.** 7. CONTROLLED BUILD-AHEAD (constrain.py:120-121): lift the hard cap 'never produce more than the month's own demand' to allow production up to (demand + target_anticipation_inventory) in pre-peak months, bounded by capacity and a carry cost. This restores the level-strategy lever (one of three canonical aggregate-planning strategies currently missing) and turns the spring/Q4 seasonality encoded in datagen.py from a lost-sale source into a managed plan. Gate behind a flag so the current simpler story remains available.
**8.** 8. IBCS-COMPLIANT COCKPIT (dashboard.py): compute ONE shared y-axis domain per metric-unit across base+upside+constrained and apply it to every panel (shared_scale_for(unit) helper); never let a panel auto-scale from its own series. Add a side-by-side 'all scenarios' overlay mode to the capacity and gap charts. Replace any gauge/donut/speedometer with bullet graphs (value + target tick + qualitative bands) for utilization/fill-rate. Add a vertical waterfall for the margin bridge (base margin -> +upside lift -> -constrained penalty -> realized margin). Kill dual-y-axis, pies, 3D, gradient fills, drop shadows. Adopt IBCS notation: solid=actual/plan, hollow/hatched=forecast/constrained, color (diverging red/green) reserved strictly for variance from base.
**9.** 9. GRADED BOTTLENECK DISPLAY (capacity.py:68 + dashboard.py): replace the binary is_bottleneck (utilization>100%) with a graded scale — safe <85%, strained 85-95%, critical >95% (thresholds configurable) — backed by Hopp & Spearman's Kingman VUT equation (queue time roughly doubles from 90% to 95%). Show the bottleneck's utilization AND its capacity cushion (100% - utilization); optionally overlay the VUT curve so executives see why 97% is qualitatively worse than 90%. Keep >100% as the hard infeasible ceiling. Promote binding_resource() (capacity.py:88) to a headline callout.
**10.** 10. SCOR-ALIGNED KPI ADDITIONS + IBP RECONCILIATION LINE (kpi.py + dashboard.py): add inventory turns (COGS / avg inventory value) and inventory days (365 / turns) — the repo already has ending inventory value, so this is one derived line; OEE for the bottleneck Assembly Line A (Availability x Performance x Quality inputs in datagen); perfect-order % (fill rate decomposed into on-time + complete + damage-free); schedule attainment. Gate which render to avoid clutter. Add an explicit revenue/margin TARGET (budget/commit) input per scenario and surface a gap-to-plan ($ and %) line — this is the integrated reconciliation step that defines IBP over classic S&OP, currently missing.
**11.** 11. REALISTIC PARAMETERS + REPRODUCIBILITY (datagen.py + families data): recalibrate opening_inventory_units to ~60-90 days of supply (Whirlpool ~61, LG ~59 days; current levels sit 15-30% low and read as under-stocked for a seasonal peak); add per-family production_lead_time_weeks (4-6) and min_lot_size (200-500) so production must be committed ahead and snapped to lots — the mechanism that makes build-ahead and backorder logic meaningful; add a gentle 3-6%/yr growth trend so the level slopes up across the year (genuine multiplicative-on-trend seasonality, currently flat-level); optional Kitchen/Laundry division rollup above the 6 families for an aggregate view (do NOT add SKUs). Add a --seed CLI flag defaulting to 20260714, stamp {seed, generated_at} into comparison.json, and seed a separate random.Random per noise stream using hashlib-derived sub-seeds so adding a stream later cannot perturb existing outputs. Keep numpy out.
**12.** 12. FUND-THE-BOTTLENECK INVESTMENT FRAME (finance.py + dashboard.py): add an investment_cost input for the Assembly Line A expansion (capex to lift installed hours), then derive Payback = investment_cost / annual_recovered_margin and ROI = (annual_recovered_margin - annualized_cost) / investment_cost. Surface these next to upside_value_unlocked so the 'fund the bottleneck' call has a financial frame. Keep it single-period cash flow; NPV/IRR over-engineers a demo. Converts the cockpit from 'here is the margin at risk' to 'here is the investment case to recover it.'

## Top decisions (ranked)

### 1. Scope ceiling / product identity: white-box auditable cockpit vs aspiring optimizer

**Options:**

- White-box: deterministic, multi-period, multi-scenario planning with inspectable greedy heuristics; explicitly positioned against vendor black boxes
- Aspiring optimizer: add LP/MIP + ML demand forecasting + probabilistic planning to chase feature-parity with Kinaxis/o9

**Recommendation:** White-box auditable cockpit — zero-install stdlib reproducibility + arithmetic a reviewer can eyeball is the differentiation; their black box is our white box.

**Why:** This is the master decision — everything downstream keys off it. Python stdlib has no LP/MIP solver and no ML, so any 'optimal plan' or probabilistic claim is a toy reimplementation that a practitioner debunks in one question. Five of six dimensions independently warned against crossing the solver line. The distinctive, winnable axis is transparency, not optimization. Picking optimizer also forces Stage-5 maturity targets that are unreachable without real solvers; picking white-box makes Stage 3 both sufficient and honest.

### 2. Gartner S&OP maturity target: which stage to engineer the demo to clear

**Options:**

- Stage 3 (consensus demand + forecast error/MAPE + scenarios over a horizon)
- Stage 4 (full financial scenario integration — partly already present in finance.py)
- Stage 5 (probabilistic / strategic orchestration)

**Recommendation:** Clearly clear Stage 3, visibly gesture at Stage 4 (the financial reconciliation is already half-built), do NOT attempt Stage 5.

**Why:** Stage 3 is the minimum the literature (Gartner, ASCM) accepts as 'defensible S&OP' rather than a feasibility check; below it the demo reads as short-term volume balancing. Stage 3 is reachable entirely with auditable mechanisms (seeded forecast noise, consensus override, scenario what-ifs). Stage 5 requires probabilistic forecasting and strategic models that need real solvers — unreachable and over-complicating for a showcase. State the target stage explicitly in docs/02-sop-ibp-method.md so reviewers judge the demo against a named bar.

### 3. Demand representation: deterministic truth vs forecast/actual split with uncertainty cone

**Options:**

- Deterministic single number per family/month (current — the +/-3% seeded jitter is demand-shaping, not forecast error)
- Forecast vs actual split: correlated series, seeded Normal noise at 15-30% MAPE, P10/P50/P90 cone, MAPE + bias KPI, consensus-demand step

**Recommendation:** Forecast/actual split with a P10/P50/P90 cone, MAPE and bias per family, and a consensus-demand reconciliation step.

**Why:** This is the single most-repeated demand across the methodology, data, and financial dimensions — Gartner places genuine S&OP value only once consensus demand and MAPE tracking exist. It is the M5-competition standard. It is fully auditable (seeded Normal noise, no solver), it does more for methodological credibility than any other change, and it is the prerequisite that makes the rolling re-plan, backorder, and margin-bridge views meaningful. Keeping demand deterministic pins perceived maturity at Stage 2 regardless of what else is fixed.

### 4. Rationing-rule correction altitude: one-line TOC fix vs add an LP solve

**Options:**

- TOC fix only: change constrain.py:86 sort key from f.unit_margin to f.unit_margin / f.resource_hours_per_unit[resource.id] (contribution per bottleneck-hour); keep ONE binding constraint in the dataset so the greedy heuristic provably equals the LP optimum
- Add an optional stdlib Simplex LP over families x months x resources to guarantee optimality under multiple simultaneous binding constraints

**Recommendation:** TOC one-line fix + keep exactly ONE binding resource in the demo dataset; document the heuristic's exact-when-one-constraint boundary in implementation-notes.md.

**Why:** The current rule is the textbook Goldratt error — it ranks by dollars-per-unit and ignores bottleneck-hour consumption, so it can prefer a $100-margin/5-hour product over a $40-margin/1-hour product that is twice as profitable per scarce hour. The fix is the single highest-value technical correction and it is debunk-proof. Adding LP buys optimality only when MULTIPLE constraints bind simultaneously, but (a) it adds an algorithm the audience cannot eyeball (breaking the white-box promise), (b) it tempts overclaiming into 'optimizer' territory, and (c) a second binding constraint can be AVOIDED in the dataset so the heuristic stays provably exact. Keep the dataset honest: one constraint, heuristic = optimum.

### 5. Rolling cycle depth: how much 'cycle' to prove vs the current static forward pass

**Options:**

- Surface the ALREADY-PRESENT rolling inventory balance (constrain.py:143 carries opening<-ending) as a first-class days-of-cover chart + KPI, plus ONE illustrative 'frozen actual / rolling plan' panel where 2-3 months of diverging actuals re-base the plan
- Full multi-pass rolling machinery: month-by-month re-plan ingesting actuals across all 12 months
- Keep the static single forward pass (current)

**Recommendation:** Surface the existing rolling balance (days-of-cover KPI + inventory-position-over-time chart) and add a single illustrative 2-3 month re-plan panel. Do NOT build full multi-pass machinery.

**Why:** RESOLVES A CONTRADICTION in the findings: the Dim-4 claim of 'no month-over-month propagation' is factually wrong — constrain.py:143 already rolls Opening->Ending each month. The real gaps are (1) nothing surfaces this to the viewer (no days-of-cover KPI or chart) and (2) the plan is one static pass with no re-baselining against actuals. Surfacing + one demo panel makes the 'monthly cycle' visible rather than asserted, at low code cost. Full multi-pass re-planning is the most code of any option and is the machinery most likely to tip the piece toward toy-optimizer territory.

### 6. Backorder policy: per-family stockout_policy vs lost-sale-only

**Options:**

- Per-family stockout_policy field (backorder|lost_sale); constrain.py carries backlogged units into next month's demand; add backlog KPI; default durable families (refrigerators, ranges) to backorder, impulse (microwaves) to lost-sale
- Keep lost-sale-only but make the policy explicit and family-configurable (current code forces all unmet demand to lost sale, SPEC.md:106-108)

**Recommendation:** Per-family stockout_policy with backorder carry-forward and a backlog KPI; default durables to backorder.

**Why:** The blanket lost-sale rule is a modeling choice, not the literature's default — aggregate-production planning treats backorder-vs-lost-sale as a product/customer-dependent decision and a core lever of the capacity-inventory-service triangle. For durable consumer goods (appliances), backordering is the realistic default: customers wait for a refrigerator. A blanket lost-sale rule understates the value of capturing upside and overstates the margin loss in the CONSTRAINED scenario. This is auditable realism (carry-forward arithmetic, no solver) and resolves the 'realism vs honesty' tension the benchmark dimension raised — backorder carry does NOT cross into optimizer territory.

### 7. Allocation-rule posture: single prescribed rule vs switchable policy comparison

**Options:**

- Single rule: throughput-per-constraint (the financially-maximizing one), cleaner narrative
- Switchable per-scenario: throughput-per-constraint (TOC default) / fair-share (proportional to demand) / strategic-priority (user-set score)

**Recommendation:** Switchable allocation rule with three modes; default throughput-per-constraint.

**Why:** Real S&OP does the latter — pre-S&OP reconciliation EXISTS to compare policy alternatives, and a cockpit that only shows one rule sidesteps the actual decision the committee makes. Fair-share/proportional is the principled alternative when margin ranking is strategically wrong (it protects channel relationships) and is uniquely path-consistent under any distribution topology. Turning the cockpit into a policy-comparison tool is the differentiated value a white-box demo can offer that a black-box optimizer structurally cannot. Minimal extra code; large narrative payoff.

### 8. Visualization posture: strict IBCS shared-scale + side-by-side vs per-panel smart scaling + tabs

**Options:**

- Strict IBCS: one shared y-axis per metric-unit across every panel, side-by-side scenario overlay, bullet graphs for KPIs, vertical waterfall for margin bridge, kill dual-axis/pies/gauges/3D, graded bottleneck danger zone
- Per-panel 'smart' auto-scaling with scale-indicator badges, scenario tabs (current), modern colored design

**Recommendation:** Strict IBCS: shared scale, side-by-side, bullet graphs, waterfall, graded bottleneck thresholds, IBCS notation (solid/hollow/hatched) with color reserved for variance.

**Why:** This is the repo's stated top pain, and IBCS (now ISO 24896), Few, and Tufte are unusually unified and prescriptive: charts meant for eye-comparison MUST share scales and zero baselines; dual-y-axis charts are the worst-performing type in the only peer-reviewed study of them (Isenberg 2011: worst on accuracy AND time, ranked lowest by 14/15 participants); Kingman's VUT equation shows cycle time explodes nonlinearly near 100% so the binary >100% flag understates risk. Side-by-side is also the universal vendor pattern (Kinaxis/o9/SAP IBP/Blue Yonder), so strict IBCS satisfies both the science and the market. The current per-scenario tabs are orthogonal to how every leading cockpit works.

### 9. 'Gross margin' field: rename to contribution margin vs also compute true gross margin

**Options:**

- Rename only: unit_margin -> contribution_margin everywhere (models.py, finance.py, kpi.py, dashboard.py, docs); the math is already correct (price - variable cost)
- Also compute a true gross-margin line with allocated fixed overhead so the exec P&L shows both

**Recommendation:** Rename to contribution margin everywhere; do NOT add true gross margin.

**Why:** This is a correctness fix, not cosmetic — the field lies to an executive reader today. But adding true gross margin requires a fixed-overhead allocation basis, which reintroduces the very arbitrariness (rent, depreciation, salaried overhead allocated subjectively) that IBP and throughput accounting exist to eliminate. Two products with identical 15% gross margins can have wildly different contribution margins, and gross margin can make a positive-contribution product look unprofitable, triggering a wrong drop decision. For a capacity-allocation cockpit, contribution is the only decision-relevant metric. Keep the allocation out.


## Cross-cutting themes

- MASTER FRAME: the white-box-vs-optimizer identity is the single arbiter every recommendation must pass through. Any 'realism' addition (backorders, build-ahead, lot-sizing, forecast cones) is IN if it stays eyeball-auditable with stdlib arithmetic, and OUT if it requires an LP/MIP solver, ML, or a graph data model. This resolves the central contradiction between the methodology dimension (push to Stage 3/4) and the benchmark dimension (don't become a toy) — Stage 3 is reachable in white-box; Stage 5 is not, and must not be attempted.
- DEDUP — TOC throughput-per-bottleneck-hour ranking: the methodology, capacity, and financial dimensions all independently flag the SAME bug (constrain.py:86 sorts by per-unit margin, the classic Goldratt error). It is the single highest-value, lowest-cost technical correction. The data needed (resource_hours_per_unit) already exists in models.py.
- DEDUP — forecast uncertainty / MAPE / consensus demand: appears in both the methodology and data dimensions as the #1 credibility gap. Gartner places genuine S&OP value only once MAPE tracking and consensus demand exist. This is the most-repeated demand across all six dimensions and the prerequisite that makes the rolling re-plan, backorder carry, and margin-bridge views meaningful.
- CONTRADICTION RESOLVED — rolling inventory balance: the data dimension claims 'no month-over-month propagation,' but constrain.py:143 (`opening[family.id] = ending`) ALREADY rolls Opening->Ending each month. The engine has the balance; what is missing is (a) a days-of-cover KPI and inventory-position-over-time chart that surface it, and (b) the rolling RE-PLAN against actuals (the plan is one static forward pass because there is no forecast/actual distinction to re-base against). The fix is surfacing + one demo panel, not a rebuild.
- DEDUP — IBCS visualization: the viz-science and tool-benchmark dimensions reinforce each other (shared scales + side-by-side scenario comparison + IBCS notation). Every leading vendor cockpit (Kinaxis/o9/SAP IBP/Blue Yonder/OMP) uses side-by-side what-if comparison; the current repo uses one-scenario tabs, which is orthogonal to the dominant pattern. Shared scales is also the repo's stated top pain.
- CORRECTNESS — 'gross margin' mislabel: the field is mathematically contribution margin (price - variable cost). Rename is a correctness fix, not cosmetic. Do NOT add true gross margin with allocated overhead — it reintroduces the arbitrariness IBP exists to avoid.
- FINANCIAL FRAMING GAP — fund-the-bottleneck: the cockpit currently shows only the numerator (upside_value_unlocked = $531,728 annual margin-at-risk) with no denominator (capital outlay). Nucleus Research's framework says an investment case needs Payback and ROI. Add investment_cost input + derived payback/ROI to convert the narrative from 'here is what we lose' to 'here is whether to invest.'
- FACTUAL CORRECTION — the prompt's 'single-period' premise is inaccurate: the code is a 12-month plan with month-to-month inventory carry (MONTHS = range(1,13), constrain.py:143). The revamp narrative should correct this framing, not work around it; the real gaps are no rolling re-plan, no demand uncertainty, no backorders, no build-ahead, no consensus/exec tiers.
- HONEST LIMITATION AS STRENGTH — RCCP is openly criticized by practitioners (River Logic: 'feasible but not optimal'; RELEX: 'snapshot view'). The repo already leans on this honestly. Convert the acknowledged limitation into the documented rationale for the white-box approach: the cockpit exposes the feasibility-and-bottleneck gap rather than hiding it inside an optimizer. Label the engine precisely as 'greedy TOC heuristic' everywhere (README, dashboard exec-takeaway, kpi-reference) so the repo never overclaims.

## Findings by dimension

### Dimension 1: S&OP / IBP methodology rigor

**Confidence:** high  |  **Findings:** 8  |  **Choices:** 6

The literature (APICS/ASCM, Wallace & Stahl, Oliver Wight, Gartner) converges on one gold standard: a recurring monthly cycle of five phases — data update, demand planning, supply planning, pre-S&OP reconciliation, and executive S&OP — with IBP extending the same cycle by integrating finance and strategy over a 24-month rolling horizon. The Cascade Appliances repo already implements the bones correctly (RCCP feasibility, margin-priority rationing, unit+financial reconciliation in one cycle), but it hard-codes several simplifications that the literature treats as core planning levers, not optional: demand is deterministic (no forecast error / MAPE / consensus step), unmet demand is forced to lost-sale (no backorders), build-ahead/anticipation inventory is forbidden, the 12-month plan is a single static pass (no rolling re-plan), and there is no explicit pre-S&OP or executive decision tier. The single highest-leverage credibility gaps are (1) the absence of demand uncertainty and a consensus-demand number, and (2) the lost-sale-only rule, which together make the plan look more like a one-shot feasibility check than a defensible S&OP cycle.

#### Findings

**The gold-standard S&OP/IBP cycle is the Wallace & Stahl five-step monthly process (Data Update -> Demand Planning -> Supply Planning -> Pre-S&OP Reconciliation -> Executive S&OP), and this is the frame APICS/ASCM teach.**

_Evidence:_ Multiple independent academic and practitioner sources cite Wallace & Stahl's (2006) five-step model as the reference standard. A Brazilian multi-company study states it 'uses Wallace and Stahl's (2006) five-step model as a reference to describe the standard S&OP cycle-steps.' ASCM frames S&OP as 'an integrated business management process through which an executive team continually achieves focus, alignment and synchronization among all business functions.' The repo's own docs/02-sop-ibp-method.md maps onto these five steps but collapses steps 4-5 into the UPSIDE/CONSTRAINED scenario split and a dashboard artifact, rather than representing them as distinct decision tiers.

_Implication for repo:_ Keep the five-phase spine, but make Pre-S&OP and Executive S&OP first-class stages in the pipeline (their own module/panel), not just an implicit scenario split. The dashboard should render a 'recommendation' emerging from a pre-S&OP reconciliation step and an 'approved plan' from an exec gate, so the cycle is visible, not just the arithmetic.

_Sources:_

- S&OP: Learnings from 15 Brazilian Companies (references Wallace & Stahl 5-step model) (2018) — https://scispace.com/pdf/sales-and-operations-planning-learnings-from-15-brazilian-14i2mpabbd.pdf
- ASCM Insights — Making the Case for Integrated Business Planning (2023) — https://www.ascm.org/ascm-insights/making-the-case-for-integrated-business-planning/
- Advanced S&OP Process Improvement (diva-portal, references Wallace 2004) (2023) — https://www.diva-portal.org/smash/get/diva2:1698576/FULLTEXT02.pdf

**IBP's defining move over classic S&OP is integrating the financial plan (revenue, margin, inventory value) into the same cycle over a longer (~24-month) horizon — exactly what the repo already does with finance.py, so this is a strength to preserve and surface.**

_Evidence:_ ASCM's IBP article defines IBP as 'ensuring continuous alignment among demand, inventory, supply and manufacturing plans... and between the tactical and strategic business plans,' and stresses 'evaluat[ing] both financial and volumetric performance' in 'one comprehensive plan.' The repo already mixes operating KPIs (fill rate, utilization) with financial ones (gross margin, lost margin, upside unlocked) in a single kpi.py catalog — deliberately not two reports — which is precisely the IBP integration the literature calls for.

_Implication for repo:_ No structural change needed in finance.py — but extend the planning horizon visibly beyond the current 12 months (or label the tail months as the strategic/IBP band) so the S&OP-to-IBP progression is explicit in the dashboard, matching the literature's 18-24 month IBP horizon.

_Sources:_

- ASCM Insights — Making the Case for Integrated Business Planning (2023) — https://www.ascm.org/ascm-insights/making-the-case-for-integrated-business-planning/
- Global Sales and Operations Planning: A Multinational Study (PMC) (2021) — https://pmc.ncbi.nlm.nih.gov/articles/PMC8454961/

**The biggest methodological gap is that the repo's demand is deterministic: the seeded +/-3% jitter in datagen.py is demand-shaping, not forecast ERROR, and there is no forecast-vs-actual distinction, no MAPE, no bias, no consensus demand number. The literature treats forecast accuracy and a consensus 'one-number' demand plan as the engine of the whole cycle.**

_Evidence:_ Gartner's demand-planning research is built on forecast-error measures (MAPE and bias) as the primary lever to improve outcomes, and documents that a modest forecast-accuracy gain drives disproportionate service and inventory benefits (a Gartner-cited rule of thumb: a 6% forecast improvement yields ~10% better perfect-order and 10-15% less unnecessary inventory). ASCM's 9-step IBP checklist makes consensus demand and what-if simulation central. Gartner's maturity model only reaches value-generating Stage 3+ once consensus demand planning and MAPE tracking exist; below that, S&OP is just short-term volume balancing.

_Implication for repo:_ Split the deterministic demand into a FORECAST (the plan) and an ACTUAL (realization), compute MAPE and bias per family, and add a 'consensus demand' step where a marketing/sales override is reconciled with the statistical baseline. Add forecast_accuracy and forecast_bias to kpi.py. This single change does more for methodological credibility than any other.

_Sources:_

- Gartner — Expose Forecast Error Root Causes to Improve the Demand Planning Process (2024) — https://www.gartner.com/en/documents/6892666
- Forecast Accuracy / MAPE benchmark guide (references Gartner weighting guidance) (2026) — https://roadmap-tech.com/2026/05/21/what-is-forecast-accuracy-2026-benchmarks/
- Measuring Forecast Accuracy — Getting Started (cites Gartner 6%/10%/10-15% rule) (2015) — https://www.tecsys.com/blog/2015/02/measuring-forecast-accuracy-getting-started

**Gartner's S&OP maturity model (4-stage historically, now 5-stage: React/Anticipate -> Respond -> Integrate/Consensus -> Collaborate -> Orchestrate) places genuine business value only at Stage 3+, where consensus demand, scenario integration, and financial alignment appear. A demo frozen at deterministic single-pass volume balancing reads as Stage 2.**

_Evidence:_ Gartner's five-stage model is widely summarized: Stage 1 no shared goals; Stage 2 operational/volume sales planning; Stage 3 demand-and-supply balancing with consensus; Stage 4 cross-functional/financial integration; Stage 5 enterprise/strategic orchestration. ToolsGroup notes 'Stage 4 maturity is key to Gartner's analysis' of S&OP software, and the Emerald peer-reviewed study links maturity progression to measurable performance. The repo's margin-priority rationing and financial reconciliation already point at Stage 4, but the absence of consensus demand and forecast error pins the perceived maturity at Stage 2.

_Implication for repo:_ Pick a target maturity stage explicitly in the docs and engineer the demo to visibly clear it. Reaching 'Stage 3 credible' requires: consensus demand + forecast error/MAPE + scenario what-ifs over a horizon. State the target stage in docs/02-sop-ibp-method.md so reviewers can judge the demo against a named bar.

_Sources:_

- The 5 S&OP Maturity Levels (Gartner model summary) (2024) — https://www.jedox.com/en/blog/5-sop-maturity-levels/
- Gartner's Five Stages of Supply Chain Planning Technology Maturity (2023) — https://www.toolsgroup.com/blog/gartners-five-stages-of-supply-chain-planning-technology-maturity/
- Enhancing Sales and Operations Planning Maturity (Emerald, peer-reviewed) (2025) — https://www.emerald.com/bpmj/article/31/6/2579/1249053/Enhancing-sales-and-operations-planning-maturity

**Forcing all unmet demand to be a lost sale (SPEC.md line 106-108, constrain.py) is a modeling choice, not the literature's default. Aggregate production planning treats backorder-vs-lost-sale as a product/customer-dependent decision and a core lever of the capacity-inventory-service triangle.**

_Evidence:_ The aggregate-planning literature explicitly frames the choice among capacity, inventory, and backlog/lost-sales as the central tradeoff, and distinguishes backorders (demand held for future production) from lost sales (customer walks). Recent peer-reviewed work formulates aggregate planning explicitly to optimize service level under this tradeoff. For durable consumer goods like appliances, backordering is the realistic default for constrained families — customers wait for a refrigerator — so a blanket lost-sale rule understates the value of capturing upside and overstates the margin loss in CONSTRAINED.

_Implication for repo:_ Make backorder-vs-lost-sale a per-family policy field in families.json (e.g. backorder_fraction or stockout_policy), and have constrain.py carry backlogged units into next month's demand. Add a backorder_value/backlog KPI. For the demo, defaulting durable families (refrigerators, ranges) to backorder and impulse families (microwaves) to lost-sale would itself be a defensible planning narrative.

_Sources:_

- Optimal Control Approaches to the Aggregate Production Planning Problem (MDPI, peer-reviewed) (2015) — https://www.mdpi.com/2071-1050/7/12/15819
- Proposed Aggregate Planning for Overcoming Overstock and Shortage (ResearchGate, peer-reviewed) (2025) — https://www.researchgate.net/publication/393854792_Proposed_Aggregate_Planning_for_Overcoming_Overstock_and_Shortage_at_La_Creme

**The repo forbids build-ahead / anticipation inventory ('never produce more than the month's own demand', constrain.py line 120-121), which removes two of the three classic aggregate-planning strategies (level and chase/hybrid) and leaves only within-month rationing.**

_Evidence:_ Aggregate-planning pedagogy defines three canonical strategies — Level (steady production, build anticipation inventory for peaks), Chase (vary production to follow demand), and Hybrid/Tailored — all revolving around pre-building stock in low-demand months to cover peaks. By forbidding production above current-month demand, the repo collapses the strategy space and makes seasonality (the spring/Q4 bumps encoded in datagen.py) un-addressable except by lost sales or capacity investment. This is the one simplification that most undercuts the 'planning' framing.

_Implication for repo:_ Allow controlled build-ahead: produce up to (demand + target_anticipation_inventory) in pre-peak months, capped by capacity and carrying cost. Even a simple 'anticipation stock' toggle that pre-builds for the Q4 holiday bump would demonstrate the level-strategy lever and turn seasonality from a lost-sale source into a managed plan.

_Sources:_

- Optimal Control Approaches to the Aggregate Production Planning Problem (MDPI, level plan with inventory/backlog/lost-sale) (2015) — www.mdpi.com/2071-1050/7/12/15819
- Mastering Aggregate Planning — Level vs Chase vs Hybrid strategies (2024) — https://medium.com/@the-open-collective/mastering-aggregate-planning-your-essential-guide-to-forecasting-strategies-and-outsourcing-cec704344375

**The 12-month plan is computed in one static forward pass with no rolling re-plan. Real S&OP/IBP is a rolling horizon: the plan is re-baselined every month as actuals replace forecasts, which is what makes it a recurring cycle rather than an annual budget.**

_Evidence:_ The peer-reviewed rolling-horizon literature defines the discipline as replanning periodically as time advances and uncertainty resolves, and treats it as the defining mechanism of tactical supply planning. ASCM and practitioner sources describe S&OP as a monthly rolling process on an 18-24 month horizon. The repo's build_supply_plan loops once over MONTHS using the fixed seeded demand — correct as a single iteration, but it never shows the plan being re-based against actuals, so the 'monthly cycle' framing is asserted rather than demonstrated.

_Implication for repo:_ Add at least an illustrative rolling-horizon step: simulate 2-3 months of 'actuals' diverging from forecast, then re-run the plan from the current month forward and show how the constrained recommendation shifts. A 'frozen actual / rolling plan' view in the dashboard would visibly demonstrate the cycle, not just the arithmetic.

_Sources:_

- Rolling Horizon Planning in Supply Chains: Review, Implications and Directions (Sahin, Narayanan & Robinson, peer-reviewed) (2013) — https://www.researchgate.net/publication/263110353_Rolling_horizon_planning_in_supply_chains_Review_implications_and_directions_for_future_research
- A Multi-Product and Multi-Period Inventory Planning Model (MDPI, peer-reviewed) (2025) — https://www.mdpi.com/2305-6290/9/4/151

**The KPI catalog (kpi.py) is missing the measures the literature uses to judge an S&OP plan: forecast accuracy/MAPE and bias, inventory days-of-cover or turns, backorder/backlog value, and a service-level metric beyond unit fill rate.**

_Evidence:_ Gartner's demand-planning research centers on MAPE/bias; ASCM's IBP checklist requires evaluating 'financial and volumetric performance' together, which implies inventory-value-rotation (turns/days) and service-level (not just fill) KPIs; the aggregate-planning literature tracks backlog and inventory level jointly. The repo measures fill_rate, utilization, revenue, margin, lost margin, upside value, and ending inventory value — strong on financial outcome, silent on forecast quality, inventory efficiency, and backorder exposure.

_Implication for repo:_ Extend kpi.py with: forecast_accuracy (MAPE) and forecast_bias per family, inventory_days_of_cover (= ending inventory / avg daily demand), backorder_value (once backorders exist), and a service_level distinct from fill_rate (e.g. line-fill or order-fill). Surface these in the dashboard KPI tile row so the plan is judged on the dimensions a real S&OP committee uses.

_Sources:_

- Gartner — Expose Forecast Error Root Causes (MAPE/bias as core demand-planning measures) (2024) — https://www.gartner.com/en/documents/6892666
- ASCM Insights — evaluate financial AND volumetric performance in one plan (2023) — https://www.ascm.org/ascm-insights/making-the-case-for-integrated-business-planning/
- Optimal Control Approaches to Aggregate Production Planning (MDPI, joint backlog/inventory/service tracking) (2015) — https://www.mdpi.com/2071-1050/7/12/15819

#### Choices for Lavi

- Maturity target. Stage 3 (consensus demand + forecast error/MAPE + scenarios) is the minimum for the demo to read as defensible S&OP rather than a feasibility check; Stage 4 (full financial scenario integration) is partly already there; Stage 5 (probabilistic/strategic) risks over-complicating a showcase. Decide where to draw the line — my recommendation is 'clearly Stage 3, gesture at Stage 4.'
- Demand-uncertainty representation. Two credible options: (a) deterministic forecast + a stated MAPE/bias and a simple +-fan (readable, low code) vs (b) Monte Carlo scenarios over demand realizations (rigorous, shows risk, more code and a heavier dashboard). Pick the one that matches whether the demo's pitch is 'clean S&OP narrative' or 'risk-aware planning.'
- Backorder policy scope. Model backorders as first-class (per-family stockout_policy, backlogged units carry forward, backlog KPI — more realistic, more moving parts) vs keep lost-sale-only but make the policy explicit and family-configurable (simpler, still a defensible narrative for impulse goods). This is the scope/realism tradeoff with the biggest effect on how the CONSTRAINED scenario reads.
- Rolling horizon depth. Implement a genuine month-by-month re-plan that ingests diverging actuals (most rigorous, most code, best demonstrates the 'cycle') vs show a single 12-month rolling view that re-bases once as an illustrative panel (lighter, still visible). Decide how much 'cycle' the demo needs to prove.
- Process-tier visibility. Promote Pre-S&OP and Executive S&OP to explicit pipeline stages with their own dashboard panels (process fidelity, more panels) vs keep them implicit in the scenario split and frame the dashboard as the exec-S&OP artifact (leaner, current design). Note: the prompt describes the repo as 'single-period'; the code is actually 12-month with month-to-month inventory carry — confirm whether you want me to treat the spec or the prompt's framing as the gap baseline.
- Factual clarification for the team. The prompt's 'single period' premise is inaccurate against the current code: SPEC.md and constrain.py show a 12-month plan with opening->ending inventory carry each month. The real gaps are no rolling re-plan, no backorders, no build-ahead, no demand uncertainty, no consensus/exec tiers. Decide whether the revamp narrative should correct this framing or work around it.

### Dimension 2: Capacity planning under constraint (RCCP): is margin-priority rationing defensible, which allocation rule is right for an S&OP cockpit, and how should bottleneck utilization be computed and displayed?

**Confidence:** high  |  **Findings:** 7  |  **Choices:** 4

The repo's current "descending unit_margin" rationing (constrain.py line 86) is the textbook wrong rule: it ranks families by dollars-per-unit and ignores how many scarce-resource hours each unit consumes. This is exactly the error Goldratt's Throughput Accounting was created to expose — the correct TOC ranking is throughput (contribution) PER UNIT OF THE BOTTLENECK resource ($/bottleneck-hour), which diverges from per-unit margin whenever families consume different bottleneck hours. Even that corrected rule is only provably optimal for a single binding constraint; with multiple simultaneous binding constraints, only LP finds the true optimum, and the repo's current MIN-across-resources is an ad-hoc greedy heuristic. RCCP at family/aggregate level is, however, the correct granularity for an S&OP (not shop-floor) cockpit per Vollmann/Berry/Whybark/Jacobs. Finally, the flat >100% bottleneck flag misleads: Hopp & Spearman's Kingman VUT equation shows cycle time and WIP explode nonlinearly as utilization approaches 100%, so a "danger zone" well below 100% and a visible capacity cushion are the correct way to display bottleneck health.

#### Findings

**Margin-priority rationing as currently coded (sort by per-unit margin, allocate scarce hours top-down) is NOT the TOC rule and is the classic Goldratt error: the correct ranking metric is throughput (contribution) per unit of the bottleneck resource, not per-unit margin.**

_Evidence:_ Throughput Accounting ranks products by (Selling Price - Totally Variable Costs) / Time-on-bottleneck = $/bottleneck-hour, then greedily allocates the bottleneck's capacity in that order. Per-unit margin ignores bottleneck consumption entirely, so 'a product with a high fully-absorbed per-unit margin might actually consume large amounts of bottleneck capacity, generating relatively little throughput per constraint hour.' The 6Sigma source states the method explicitly: rank by throughput per bottleneck unit, not by per-unit profit; cost accounting 'can mislead by showing unprofitable products as profitable.' The repo's models.py line 101-102 defines unit_margin = unit_price - unit_variable_cost (pure $/unit), and constrain.py line 86 sorts users by f.unit_margin descending — denominator-free. If Family A has $100 margin and uses 5 bottleneck-hours/unit and Family B has $40 margin and uses 1 bottleneck-hour/unit, the code prefers A ($20/bottleneck-hr) when B ($40/bottleneck-hr) is twice as profitable per scarce hour.

_Implication for repo:_ In constrain.py _allowed_units_this_month, change the sort key from f.unit_margin to f.unit_margin / f.resource_hours_per_unit[resource.id] (throughput per bottleneck-hour on THIS resource). This is the single highest-value correction in the dimension. For a multi-resource family, rank separately per resource since the binding resource differs; the MIN-across-resources step already preserves feasibility.

_Sources:_

- Throughput Accounting (Theory of Constraints) — 6Sigma.us (2024) — https://www.6sigma.us/six-sigma-in-focus/throughput-accounting/
- Throughput Accounting step-by-step product-mix method (Scribd notes) (2021) — https://www.scribd.com/document/519344024/Throughput-Accounting-F5-notes
- Is Throughput-per-Constraint-Unit Truly Useful? — Eli Schragenheim (2016) — https://elischragenheim.com/2016/08/27/is-throughput-per-constraint-unit-truly-useful/

**Even the corrected throughput-per-constraint-unit rule is provably optimal ONLY for a single binding constraint; with two or more simultaneous binding resources, greedy ranking can be suboptimal and only linear programming finds the true optimum.**

_Evidence:_ The TOC heuristic ranks by throughput per bottleneck-minute and greedily fills; it equals the LP optimum when exactly one constraint binds, but with multiple active constraints 'the greedy ranking doesn't account for interactions between constraints.' The Industria Textila 2022 paper explicitly compares the TOC heuristic against LP to define the optimal product mix under multiple constraints and shows where the heuristic diverges. The PMC/NIH 2022 paper combines TOC bottleneck identification with LP to recover the true optimum.

_Implication for repo:_ Document the engine as a TOC-style heuristic that is exact when one resource binds and approximate when several do (the MIN-across-resources in constrain.py is the approximation). If exactness is wanted, add an optional LP solve (stdlib-only: a small Simplex over families x months x resources maximizing sum(unit_margin x produced) subject to per-resource hour caps). Keep LP behind a flag so the default stays auditable.

_Sources:_

- Determining the Optimal Product Mix in Multiple Constraints (Industria Textila) (2022) — https://www.revistaindustriatextila.ro/images/2022/5/012%20AKMAN%20GULSEN%20INDUSTRIA%20TEXTILA%20no.5_2022.pdf
- A Linear Programming Methodology to Optimize Decision-Making (PMC/NIH) (2022) — https://pmc.ncbi.nlm.nih.gov/articles/PMC9483369/
- Linear Programming — Product Mix Problem (UT Dallas) (2021) — https://www.utdallas.edu/~scniu/OPRE-6201/documents/LP1-Linear_Programming.html

**Fair-share / proportional rationing is the principled alternative when margin ranking is strategically wrong, and it is uniquely consistent under any distribution topology.**

_Evidence:_ The proportional rule is 'the only solution that assigns the same allocation regardless of whether the resource is distributed directly to end users or through intermediary agents' (consistency under path). It is the standard rationing scheme where unsatisfied demand is allocated as a fraction alpha of capacity (Vives 1986, cited 149x). This is what real S&OP often does to protect channel/customer relationships rather than maximise short-run margin.

_Implication for repo:_ Offer allocation-rule as a per-scenario switch in constrain.py with at least three modes: 'throughput_per_constraint' (TOC, default), 'fair_share' (proportional to demand), and 'strategic_priority' (a user-set priority score). This turns the cockpit into a policy-comparison tool, which is what pre-S&OP reconciliation is actually for.

_Sources:_

- Decentralized Rationing Problems and the Proportional Rule (Semantic Scholar) (2007) — https://www.semanticscholar.org/paper/5c568781574a4e141d3223c2e576383eb5b9e384
- Rationing Rules and Bertrand-Edgeworth Equilibria — X. Vives (1986) — https://blog.iese.edu/xvives/files/2011/09/67.pdf
- Priority Rules and Other Asymmetric Rationing Methods (ResearchGate) (2006) — https://www.researchgate.net/publication/4896376_Priority_Rules_and_Other_Asymmetric_Rationing_Methods

**RCCP at aggregate family/resource level is the correct granularity for an S&OP cockpit; detailed Capacity Requirements Planning (CRP) belongs one level down at shop-floor/order execution.**

_Evidence:_ In the Vollmann/Berry/Whybark/Jacobs MPC framework, RCCP sits between S&OP and detailed CRP: it is an aggregate, family/work-center-group feasibility check using bill-of-resources hours per unit, medium-to-long horizon, validating the production plan before commitments. CRP then takes the feasible plan and explodes it against detailed routings, open shop orders and planned MRP orders at the individual work-center/order level, short horizon. Practitioner consensus: 'RCCP protects the S&OP cycle from unrealistic commitments; CRP turns that feasible plan into an executable schedule.'

_Implication for repo:_ Keep capacity.py exactly where it is on the granularity ladder: family x resource x month, installed-hours based. Do NOT add routings, work-center orders or lot sizing — that would cross into CRP and overcomplicate an S&OP demo. The module docstring already says this correctly; the recommendation is to keep resisting the pull toward detail.

_Sources:_

- Manufacturing Planning and Control for Supply Chain Management — Vollmann, Berry, Whybark, Jacobs (Google Books) (2018) — https://books.google.com/books/about/Manufacturing_Planning_and_Control_for_S.html?id=6jKx5QFipIAC
- RCCP vs CRP: How to Plan Production Capacity (LinkedIn/Alamoodi) (2025) — https://www.linkedin.com/posts/osamah-alamoodi_rough-cut-capacity-planning-rccp-vs-activity-7396535919765274624-7-m7
- Rough-Cut Capacity Planning — RELEX Solutions (2024) — https://www.relexsolutions.com/resources/rough-cut-capacity-planning/
- Overview of Capacity Requirements Planning — Oracle Docs (2010) — https://docs.oracle.com/cd/A60725_05/html/comnls/us/crp/ccrp.htm

**The flat 'bottleneck = utilization > 100%' flag is misleading: Hopp & Spearman's Kingman VUT equation shows cycle time and WIP explode nonlinearly as utilization approaches 100%, so the real danger zone is well below 100% and the last few utilization points are by far the most expensive.**

_Evidence:_ Kingman's VUT approximation: CT_q = ((c_a^2 + c_e^2)/2) * (u/(1-u)) * t_e. The utilization term u/(1-u) diverges as u->1: the cited sensitivity table shows queue time rising 2.5 -> 5.625 -> 11.875 -> 61.875 as utilization goes 80% -> 90% -> 95% -> 99%. The page calls this 'the quantitative reason never to plan a critical resource at full load' and notes 'moving from 90% to 95% roughly doubles queue time.' A linear percentage therefore understates risk near the ceiling.

_Implication for repo:_ In capacity.py and the dashboard, replace the binary is_bottleneck (utilization>100) with a graded scale: e.g. 'safe' <85%, 'strained' 85-95%, 'critical' >95% (thresholds configurable). On the dashboard, show the bottleneck's utilization AND its capacity cushion (100% - utilization), and optionally overlay the VUT curve so executives see why 97% is qualitatively worse than 90%. Keep the >100% 'infeasible' flag as the hard ceiling, but add the softer pre-ceiling alarm.

_Sources:_

- Factory Physics — Kingman VUT Cycle-Time Approximation (MetricGate, after Hopp & Spearman) (2024) — https://metricgate.com/docs/hopp-spearman-factory-physics/
- Of Physics and Factory Physics (ResearchGate) (2014) — https://www.researchgate.net/publication/260676636_Of_Physics_and_Factory_Physics
- Factory Physics — Wikipedia (2024) — https://en.wikipedia.org/wiki/Factory_Physics

**Theory-of-Constraints DBR says the bottleneck must be exploited and everything else subordinated to it, so the cockpit should name the single binding constraint and report its utilization/effectiveness separately from non-constraints.**

_Evidence:_ DBR (Drum-Buffer-Rope): the bottleneck's rate is the 'drum' that sets the pace of the whole system; 'the capacity of the entire system is equal to the capacity of its bottleneck.' TOC's five focusing steps are identify-exploit-subordinate-elevate-repeat, so a planning cockpit's first job is to make the constraint visible and then subordinate non-constraint resources to it rather than balancing capacity everywhere. The repo already computes binding_resource() (capacity.py line 88) — the single most-overloaded resource — which is the right TOC instinct.

_Implication for repo:_ Promote binding_resource() to a first-class dashboard element: a headline callout ('THE binding constraint this plan is Assembly Line A, at 118% of installed hours') plus the exploit/subordinate implication ('add X hours OR cut Y family-hours of demand'). Contrast the binding resource's utilization against non-binding resources to show that running non-constraints at lower utilization is correct subordination, not waste.

_Sources:_

- Theory of Constraints — Lean Production (2024) — https://www.leanproduction.com/theory-of-constraints/
- Drum Buffer Rope (DBR) — Forte Labs (Goldratt) (2023) — https://fortelabs.com/blog/theory-of-constraints-105-drum-buffer-rope/
- A Drum-Buffer-Rope Action Research Case Study (ResearchGate) (2020) — https://www.researchgate.net/publication/339102979

**RCCP's traditional three techniques (Capacity Bills, Resource Profile, Bill of Resources) all measure load against installed capacity — which is exactly the design choice the repo already made by keying utilization to Resource.monthly_available_hours regardless of scenario.**

_Evidence:_ RCCP validates the production plan/MPS by comparing required capacity to available capacity at work-center-group level using bill-of-resources/capacity-bills hours-per-unit; it is a feasibility test against what you have today, before any investment decision. The repo's capacity.py docstring and Resource model make the same distinction explicit: monthly_available_hours is installed capacity, and whether to add to it (UPSIDE) or ration (CONSTRAINED) is a downstream decision in constrain.py. This is doctrinally correct.

_Implication for repo:_ No code change needed — confirm and keep the installed-vs-effective capacity split. If anything, surface it on the dashboard: label every utilization figure 'vs installed capacity' and show the UPSIDE scenario's added hours as a delta on top of installed, so the audience sees the investment decision explicitly rather than as a mysteriously higher ceiling.

_Sources:_

- Rough Cut Capacity Planning (RCCP) Case Study (ResearchGate) (2021) — https://www.researchgate.net/publication/350471010_Rough_Cut_Capacity_Planning-RCCP-Case_Study
- Rough Cut Capacity Planning — a place to start (Arkieva) (2023) — https://blog.arkieva.com/rough-cut-capacity-planning-a-place-to-start/
- Guide to RCCP — Anaplan (2024) — https://www.anaplan.com/blog/guide-to-rough-cut-capacity-planning/

#### Choices for Lavi

- Correction vs. redesign scope: fix the sort key to throughput-per-bottleneck-hour (a one-line TOC fix that makes the existing greedy heuristic doctrinally correct for a single binding constraint), OR go further and add an optional LP solve (stdlib Simplex) to guarantee optimality under multiple simultaneous constraints. The one-liner is defensible and far simpler; LP is 'the right answer' but adds an algorithm the audience can't eyeball. Pick the altitude for the demo.
- Allocation-policy posture: should the cockpit present ONE rule (throughput-per-constraint, the financially-maximising one) or expose the rule as a switch (throughput / fair-share / strategic-priority) so pre-S&OP becomes a policy comparison? Real S&OP does the latter; a teaching demo may prefer the cleaner single-rule narrative.
- Bottleneck-display realism: keep the simple binary >100% 'infeasible' flag (easy to explain to a CFO) or add a Hopp & Spearman VUT-aware danger zone (e.g. critical >95%) plus a visible capacity cushion? The latter is more correct but introduces a queueing concept (nonlinear congestion) the audience may not know.
- Single vs. multiple binding constraints in the dataset: does the demo's Cascade Appliances data set up ONE binding resource (where the TOC heuristic = LP optimum, so the correction looks clean) or deliberately TWO simultaneous binding resources (which showcases where heuristic and LP diverge and forces the LP conversation)? This shapes what the cockpit can honestly claim.

### Dimension 3: Executive decision-cockpit visualization (data-viz science: equal scales, chart-type selection, IBCS/Tufte/Few rules)

**Confidence:** high  |  **Findings:** 11  |  **Choices:** 5

The visualization-science literature is unusually unified and prescriptive on the cockpit's top pain. IBCS (now ISO 24896), Stephen Few, and Edward Tufte all mandate that any charts meant to be eye-compared must share identical value-axis scales and units, with zero baselines for any length-encoding marks (bars). Dual-y-axis charts are condemned by both Few ("I cannot think of a situation that warrants them") and the only peer-reviewed study on them (Isenberg et al. 2011: worst on accuracy AND time, ranked lowest by 14/15 participants). For Cascade's 3-scenario, single-period cockpit the concrete prescription is: small-multiples of horizontal bars for the structural scenario comparison, bullet graphs (Few 2005) for the utilization/fill-rate KPIs against targets, and an IBCS vertical waterfall for the margin/contribution-to-result bridge. Color must be reserved for semantics (diverging red/green for variance), not decoration — and speedometers/donuts/3D effects are explicit kill-list items. Confidence is high because the practitioner authorities (IBCS, Few, Tufte) and the one lab study agree.

#### Findings

**Charts that the viewer is meant to compare by eye MUST share identical value-axis scales, units, and zero baseline — this is the single hardest rule in the literature and directly addresses the repo's stated top pain.**

_Evidence:_ IBCS SUCCESS 'UNIFY' rule states verbatim: 'Comparisons require consistent scaling. Don't cut axes. Use the same scale for the same units. Add scaling indicators if necessary.' Stephen Few ('Information Dashboard Design'; 'Show Me the Numbers') is paraphrased across multiple derivative guides as 'quantitative scales must be consistent across multiple graphs that are meant to be compared' and that inconsistent scales force viewers to mentally re-calibrate, defeating at-a-glance comprehension. The principle is the data-viz equivalent of a single source of truth.

_Implication for repo:_ Compute ONE global y-axis domain per metric-unit and apply it to every panel that plots that unit. Concretely: derive `min`/`max` across base+upside+constrained for each metric (utilization %, fill-rate %, margin $, units), pass a shared scale to every chart rendering that metric, and never let an individual panel auto-scale from its own series. The current self-contained HTML almost certainly lets each chart auto-scale — that auto-scaling is the bug, not a feature. Add an explicit `shared_scale_for(unit)` helper.

_Sources:_

- IBCS Standards — The SUCCESS formula (UNIFY: Scaling rule) (2024) — https://www.ibcs.com/IBCS/
- Stephen Few, 'Show Me the Numbers' — use consistent scales and axes (2012) — https://wiki.rschooltoday.com/filedownload.ashx/libweb/596/989/aN15EF/Stephen%20Few%20Show%20Me%20The%20Numbers.pdf
- Practitioner's Guide to System Dashboard Design (citing Few: 'use common scales, axis and units where possible') (2018) — http://onemogin.com/observability/dashboards/practitioners-guide-to-system-dashboard-design-p2.html

**Bar/column value axes must always include zero; cutting the axis exaggerates differences and is banned by IBCS and Few. The ONLY sanctioned exception is for position-encoded marks (lines, dots), and even then only with deliberate annotation — never for bars.**

_Evidence:_ IBCS: 'Don't cut axes.' Few is strict: because bars encode quantity via LENGTH, a non-zero baseline misleads by inflating the visible ratio of bar heights. Few's 2012 Perceptual Edge dashboard competition critiques centered on exactly this. Cairo and Few allow non-zero baselines for line/dot charts (which encode POSITION, not length), but require the choice to be visible and justified.

_Implication for repo:_ For any bar/column encoding utilization or fill-rate, force the y-axis from 0 (and for utilization, to a meaningful ceiling like 100% or the capacity cap). If the team wants to show fine differences in fill rate (e.g., 92% vs 94%), do NOT crop the axis — instead use a bullet graph (see below) whose qualitative bands make the difference legible without lying about magnitude.

_Sources:_

- IBCS Standards — 'Don't cut axes' (UNIFY/Check) (2024) — https://www.ibcs.com/IBCS/
- Stephen Few, 2012 Perceptual Edge Dashboard Design Competition (critique of non-zero bar baselines) (2012) — https://www.perceptualedge.com/blog/?p=1374
- Tableau — How to spot misleading charts: check the axes (2022) — https://www.tableau.com/blog/how-spot-misleading-charts-check-axes

**Dual-y-axis charts should be eliminated entirely. They are arbitrary (the designer chooses the ratio between the two scales), invite spurious correlation, and are the worst-performing chart type in the only peer-reviewed study of them.**

_Evidence:_ Isenberg, Bezerianos, Dragicevic & Fekete (2011), 'A Study on Dual-Scale Data Charts' (LRI / IEEE): with 15 participants the superimposed dual-axis chart 'performed poorly both in terms of accuracy and time' and 'was ranked lowest by all but one participant,' called 'very confusing and demanding too much concentration.' Stephen Few's paper 'Dual-Scaled Axes in Graphs — Are They Ever the Best Solution?' concludes he 'cannot think of a situation that warrants them.' Datawrapper catalogues three deception mechanisms: arbitrary zero-baseline heights, false crossing/correlation inference, and deliberate scale manipulation.

_Implication for repo:_ Audit the rendered HTML for any chart with a left AND right y-axis (a common pattern for plotting e.g. units-shipped vs margin-% together). Remove every one. Replace with EITHER (a) two side-by-side panels with their own honest single scales, or (b) if the point is relative movement, an indexed chart rebasing both series to 100, or (c) if the point is the relationship, a connected scatterplot. For the cockpit, default to option (a) — separate small-multiple panels.

_Sources:_

- Isenberg, Bezerianos, Dragicevic, Fekete (2011), 'A Study on Dual-Scale Data Charts' — via Datawrapper summary (2011) — https://www.datawrapper.de/blog/dualaxis
- Datawrapper — Why not to use two axes, and what to use instead (2022) — https://www.datawrapper.de/blog/dualaxis
- PolicyViz — Avoiding the Dual Axis Chart (2022) — https://policyviz.com/2022/10/06/avoiding-the-dual-axis-chart/

**The 3-scenario × multiple-metric layout should be implemented as TRUE small multiples (Tufte) / faceted panels with synchronized axes — not as free-floating independent charts. IBCS explicitly says to 'synchronize the Y-axis' when breaking a chart into panels.**

_Evidence:_ Tufte: small multiples are 'the same graphical design structure repeated for each of several categories' enabling direct visual comparison — they are how comparison is done in scientific communication. IBCS UNIFY directs that when a comparison is split across panels the y-axis must be synchronized across them. Few repeatedly prescribes panels/multiples over a single overloaded chart.

_Implication for repo:_ Lay the cockpit out as a grid: rows = metrics (utilization, fill rate, margin, unmet demand), columns (or a single compared axis) = the 3 scenarios, all panels in a row sharing one y-scale. This turns the 3 scenarios into a directly comparable visual field rather than 3 isolated charts the eye must re-calibrate between. The shared-scale helper from finding #1 is what makes this safe.

_Sources:_

- Tufte's principles — Small multiples (via thedoublethink and Georgia Tech lecture notes) (2016) — https://faculty.cc.gatech.edu/~stasko/7450/16/Notes/tufte.pdf
- IBCS / Zebrabi — 'synchronize the Y-axis' across comparison panels (2024) — https://zebrabi.com/ibcs/

**Utilization and fill-rate are KPI-vs-target metrics, and the correct chart type is the bullet graph (Few 2005), not a gauge, speedometer, donut, or bare number. A bullet graph shows actual value (bar) + target (tick) + qualitative ranges (shaded bands) in minimal vertical space, and was invented specifically to replace dashboard gauges.**

_Evidence:_ Stephen Few introduced the bullet graph in 2005 'to replace the circular gauges that dominated dashboards' (Perceptual Edge, Tableau). It encodes a single measure against a target plus performance bands in far less space than a gauge, with no gauge's false precision or circular-area-encoding problem. Few also wrote specifically on bullet graphs for 'not-to-exceed targets' — the exact use case for capacity utilization where staying under a ceiling matters.

_Implication for repo:_ Replace any gauge/speedometer/donut rendering utilization or fill-rate with bullet graphs: a horizontal bar (actual fill rate / utilization) over 2–3 shaded qualitative bands (e.g., red <70%, amber 70–90%, green >90% for fill rate) with a target tick (e.g., 95% fill-rate target, 85% utilization ceiling). The bands make 'how should I feel about this KPI' answerable in under a second without cropping any axis — solving the zero-baseline-vs-fine-discrimination tension from finding #2.

_Sources:_

- Stephen Few (Perceptual Edge) — Bullet Graphs for Not-to-Exceed Targets (2008) — https://www.perceptualedge.com/blog/?p=217
- Tableau — What is a bullet graph (Few's gauge replacement) (2023) — https://www.tableau.com/chart/what-is-a-bullet-graph
- Domo — What is a bullet graph (Few 2005, replaces gauges) (2023) — https://www.domo.com/learn/charts/bullet-graphs

**The margin-attribution and scenario-reconciliation view belongs in a vertical waterfall (bridge) chart — the IBCS-prescribed chart for showing contributions/variances to a result. Bars for totals, floating steps for the increments/decrements that bridge them.**

_Evidence:_ IBCS EXPRESS: 'Prefer columns, bars, and lines to pies and gauges,' and the waterfall is the recommended form for variances and 'contributions to the overall result.' IBCS-compliant vendor examples (ZebraBI, Inforiver) standardize vertical waterfalls for P&L and margin bridges, with consistent axis scaling and standardized color for up/down variances.

_Implication for repo:_ Add a margin-bridge waterfall: start column = base-scenario margin, then a step per reconciling item (upside volume lift, constrained-capacity penalty, build-ahead carry, backorder cost), end column = the scenario's realized margin. Render one waterfall per scenario OR overlay the three end-columns for direct comparison. This replaces any stacked-bar-as-margin hack and makes the 'where did the margin go' question self-evident — a core executive question the current single-period cockpit doesn't answer.

_Sources:_

- IBCS Standards — EXPRESS (waterfall for variances and contributions) (2024) — https://www.ibcs.com/IBCS/
- How to present variance analysis using waterfall charts (FP&A) (2024) — https://fpandhey.substack.com/p/how-to-present-variance-analysis
- Inforiver — Power BI financial reporting with IBCS-compliant waterfalls (2023) — https://inforiver.com/blog/inforiver-analytics-plus/power-bi-financial-reporting-with-waterfall-charts/

**Color must encode SEMANTICS, not decoration. IBCS fixes a notation: scenarios get distinct FILL PATTERNS (solid = actual, outline = plan, hatched = forecast, gray = prior/comparison), and variance gets diverging red/green. For Cascade's three scenarios, categorical distinction should be pattern-or-hue, and any deviation metric should use a diverging palette centered on a meaningful midpoint — never a rainbow.**

_Evidence:_ IBCS UNIFY notation: solid black = actuals, outline = plan, hatched = forecast, gray = previous period; 'green denotes positive variances, red denotes negative'; 'colors should be reserved for more important things' and charts otherwise 'simple black white.' Wilke (Fundamentals of Data Visualization) and Datawrapper codify the three palette types: sequential for ordered magnitude, diverging for deviation from a midpoint, categorical/qualitative for unordered groups — and warn against using categorical colors with sequential data or vice versa.

_Implication for repo:_ (a) Assign the 3 scenarios a categorical palette (3 maximally distinguishable hues, colorblind-safe — e.g. Okabe-Ito blue/orange/green) and keep that mapping constant everywhere. (b) For any variance/shortfall metric (unmet demand, margin gap vs plan), use a diverging palette centered at zero (red below, neutral at zero, green above) — never reuse the scenario hue for this. (c) Consider adding IBCS fill patterns (solid/outline/hatched) so scenarios remain distinguishable in monochrome print and for colorblind viewers. Drop any decorative background fills, 3D, or gradients.

_Sources:_

- IBCS Standards — UNIFY scenario & variance notation (2024) — https://www.ibcs.com/IBCS/
- Datawrapper — When to use sequential vs diverging color scales (2020) — https://www.datawrapper.de/blog/diverging-vs-sequential-color-scales
- Claus Wilke, 'Fundamentals of Data Visualization' — color pitfalls (sequential/diverging/qualitative) (2019) — https://clauswilke.com/dataviz/color-pitfalls.html

**The cockpit must satisfy the executive '5-second' comprehension rule: the primary message (which scenario wins, where is capacity binding, where is margin leaking) must be perceptible in ~5 seconds. This is achieved through visual hierarchy, restraint, and a single dominant message — not by adding more charts.**

_Evidence:_ Few's 'Information Dashboard Design' frames the dashboard as a 'single screen that provides the information needed to monitor the business at a glance,' and the '5-second rule' (widely attributed to Few's at-a-glance principle) is adopted across practitioner guidance: a viewer should grasp overall status within five seconds or the dashboard needs redesign. Underpinning it is cognitive-load/perceptual grouping — preattentive attributes (position, length, color) are processed before conscious reading, so the design must put the key comparison in a preattentive channel.

_Implication for repo:_ Establish a top 'message band': one headline KPI row (the recommended scenario + its margin/fill-rate vs the others, with a clear variance color) above the detail panels. Order panels top-left → bottom-right by decision-importance (perceptual reading order). Cap the number of simultaneously-visible charts (~5–7) and remove anything that does not serve a decision. The point of the cockpit is a decision (pick a scenario / approve a plan), so the 5-second read must surface that recommendation, not just raw numbers.

_Sources:_

- Stephen Few, 'Information Dashboard Design' (at-a-glance / single-screen principle) (2006) — https://www.academia.edu/43526296/Information_Dashboard_Design
- BPR Global — KPI dashboard 7-step guide (5-second rule for executive status) (2023) — https://bprglobal.co/resources/financial-planning-analysis/kpi-dashboard-guide/
- Domo — Top 10 dashboard design mistakes (5-second rule) (2023) — https://www.domo.com/learn/article/top-10-dashboard-design-mistakes-and-what-to-do-about-them

**Maximize the data-ink ratio and eliminate chartjunk: no 3D, no gradient fills, no heavy gridlines, no shadows, no decorative axes. Every drop of ink should encode data or direct comparison. This is Tufte's foundational rule and it compounds with the equal-scales rule — chartjunk is what makes mismatched scales hard to even notice.**

_Evidence:_ Tufte's data-ink ratio = 1 − (non-data ink / total ink): 'maximize data-ink, within reason' and 'erase non-data-ink, vigorously.' Chartjunk (3D, ornament, moiré patterns, heavy frames) is the canonical non-data-ink to remove. IBCS SIMPLIFY and CHECK enforce the same discipline ('manipulated charts are a matter of fact in business communication').

_Implication for repo:_ Audit the self-contained HTML for: 3D bar effects, gradient fills, drop shadows, thick axis lines, full grid meshes, decorative backgrounds, any chart with more legend than data. Remove all of them. Prefer integrated value labels over separate value axes/gridlines (IBCS: 'Integrate labels... try to avoid value axes and grid lines'). The freed-up ink budget makes the shared-scale comparison visually dominant.

_Sources:_

- Tufte's principles — data-ink ratio & chartjunk (Georgia Tech lecture notes) (2016) — https://faculty.cc.gatech.edu/~stasko/7450/16/Notes/tufte.pdf
- data.europa.eu — Chart junk and data ink: origins (Tufte) (2023) — https://data.europa.eu/apps/data-visualisation-guide/chart-junk-and-data-ink-origins
- IBCS Standards — SIMPLIFY / CHECK (visual integrity) (2024) — https://www.ibcs.com/IBCS/

**IBCS orientation rule: structural comparisons (the 3 scenarios) belong on the VERTICAL category axis (i.e., horizontal bars), reserving horizontal category axes (vertical columns) for time series. Cascade's cockpit is structural (scenarios), not temporal (single period) — so the default scenario chart should be horizontal bars, not vertical grouped columns.**

_Evidence:_ Zebrabi/IBCS: 'Time series (months, years, quarters) belong on the horizontal axis; structural comparisons (cities, countries, projects, revenue types) belong on the vertical axis; this applies to 95% of all charts.' The rationale: horizontal labels read more cleanly, support longer scenario names, and free vertical space for stacking metrics in small multiples.

_Implication for repo:_ Render the 3 scenarios (base/upside/constrained) as horizontal bars within each metric panel, sorted by value (Few's ranking rule) so the best scenario is immediately on top. If scenario names are short and executives strongly prefer vertical grouped columns, that is an acceptable convention deviation — but flag it as a deliberate IBCS exception, not the default.

_Sources:_

- IBCS / Zebrabi — time series horizontal, structural comparisons vertical (2024) — https://zebrabi.com/ibcs/
- IBCS Standards — UNIFY: time and structure orientation (2024) — https://www.ibcs.com/IBCS/

**Kill-list of chart types and patterns that must NOT appear in an executive S&OP cockpit, per the combined IBCS/Few/Tufte consensus: pie/donut charts (for >2 slices), speedometers/gauges, 3D anything, dual-y-axis charts, area charts with overlap, and rainbow/categorical color on ordered data.**

_Evidence:_ IBCS EXPRESS: 'Prefer columns, bars, and lines to pies and gauges,' and explicitly criticizes 'speedometer charts, doughnut/donut charts, and treemaps.' Few's entire body of work rejects 3D and ornament. The dual-axis rejection is covered above. These are not stylistic preferences — each one has a documented perceptual failure mode (pie: angle estimation is poor; gauge: circular area wastes space and misleads; 3D: foreshortening distorts magnitude).

_Implication for repo:_ Grep the rendering code for any pie/donut/gauge/3D/dual-axis implementation and remove it as a first pass. Replace pies (e.g., a demand-mix share) with a 100% stacked horizontal bar; replace gauges with bullet graphs; replace any 3D bar with its 2D equivalent. This is the fastest high-confidence cleanup and it directly serves both the 5-second rule and the equal-scales rule.

_Sources:_

- IBCS Standards — EXPRESS (reject pies, gauges, donuts, treemaps) (2024) — https://www.ibcs.com/IBCS/
- Tufte's principles — avoid chartjunk, 3D, ornament (2016) — https://faculty.cc.gatech.edu/~stasko/7450/16/Notes/tufte.pdf
- Datawrapper — Why not to use two axes (dual-axis rejection) (2022) — https://www.datawrapper.de/blog/dualaxis

#### Choices for Lavi

- Scale policy — strict shared-scale vs. annotated per-panel: Adopt ONE shared y-axis per metric-unit across the whole cockpit (max cross-panel comparability, the 'correct' answer per IBCS/Few and the fix for the stated pain), OR allow per-panel 'smart' scaling with a visible scale-indicator badge on each panel (more per-panel detail, weaker at-a-glance comparison, and reintroduces exactly the misreading risk the literature warns against). Recommend shared, but Lavi owns the realism-vs-detail tradeoff.
- Scenario encoding — IBCS fill patterns vs. color-only: Go full IBCS (solid=actual/plan, outline, hatched=forecast/constrained, gray=comparison) which is monochrome-safe and colorblind-safe, OR use a 3-hue categorical palette alone (cleaner, more modern-looking, but loses print-safety and is weaker for colorblind executives). Hatching is doable in self-contained SVG but looks 'dated' to some executives. Lavi's call on rigor vs. polish.
- Scenario-chart orientation — horizontal bars (IBCS-pure) vs. vertical grouped columns (executive convention): Strict IBCS says structural comparisons = horizontal bars; many executives expect vertical grouped columns. Both are defensible; Lavi should pick based on who reads the cockpit and whether scenario names are long.
- KPI treatment — bullet graphs vs. large numeric KPI tiles: Bullet graphs (Few's recommendation) pack value+target+bands into one row and preserve the zero-baseline, but take a beat longer to read; oversized KPI number tiles with a delta arrow are faster for the 5-second rule but carry less context and can hide where a value sits relative to target. This is a genuine density-vs-speed tradeoff Lavi should make per metric (e.g., bullet graph for the 2 binding KPIs — utilization and fill rate; large tiles for headline margin).
- Headline recommendation — should the cockpit lead with a single prescribed scenario? The 5-second rule and the cockpit's decision-purpose argue for a top 'recommended scenario' band with a defensible rationale, versus a neutral side-by-side that leaves the choice to the reader. IBCS is value-neutral here; this is a product/opinion call about whether the cockpit recommends or merely informs. Lavi owns it.

### Dimension 4: Sophisticated yet comprehensible synthetic / demo data

**Confidence:** high  |  **Findings:** 10  |  **Choices:** 7

The literature is clear that believable S&OP demo data rests on five independent, individually-legible levers: (1) a seasonal decomposition whose additive-vs-multiplicative choice follows whether the seasonal amplitude scales with the level (Hyndman); (2) a forecast-vs-actual split with an explicit uncertainty cone, the standard set by the M5 competition's probabilistic quantile forecasting; (3) a product hierarchy that stays at family level for S&OP (Arkieva/ASCM) rather than collapsing to SKU noise; (4) multi-resource constraints organized around one shared bottleneck (Theory of Constraints); and (5) a rolling inventory balance (Opening + Production - Demand = Closing) which is the defining mechanic of a multi-period plan. The current repo already nails seasonality, determinism, and the shared-bottleneck story; the big gaps are the missing forecast/error cone, the missing rolling inventory balance, and the absence of lead times/lot sizes. For a durable-goods appliance maker, grounded parameter ranges are: 4-6 week production lead time, 60-90 days of supply (Whirlpool ~61, LG ~59), peak seasonality indices of 1.3-1.5 (repo's 1.35 is in range), and 15-30% monthly MAPE.

#### Findings

**Multiplicative seasonality (seasonal amplitude proportional to the level) is the correct model for appliances and the repo already uses it correctly; the only gap is a missing trend component, since the current level is flat across the year.**

_Evidence:_ Hyndman & Athanasopoulos state multiplicative decomposition is 'more appropriate' when 'the variation in the seasonal pattern... appears to be proportional to the level of the time series,' which is 'common with economic time series' (y_t = S_t x T_t x R_t). Appliance demand grows in peak months and the swing scales with volume, so multiplicative is right. The repo's _seasonal_index normalizes a raw shape to mean 1.0 and multiplies it onto avg_demand - this is textbook multiplicative seasonality done correctly. What is absent is any trend-cycle T_t component: every month's level is the same avg_demand, so the series is multiplicative-seasonality-on-a-flat-level, which is unrealistic for a 'growing' appliance maker.

_Implication for repo:_ Keep the multiplicative _seasonal_index approach. Add an optional annual growth-rate parameter (e.g. +3-6%/yr, a realistic durable-goods range) so the level T_t slopes gently upward across the 12 months rather than being flat, making the seasonality genuinely multiplicative-on-a-trend. Gate it behind a flag so the flat version remains available for the simpler story.

_Sources:_

- Forecasting: Principles and Practice (3rd ed.) - 3.2 Time Series Components (2021) — https://otexts.com/fpp3/components.html
- Additive and Multiplicative Models - Minitab Support (2024) — https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/time-series/supporting-topics/time-series-models/additive-and-multiplicative-models/

**The single biggest sophistication gap is that demand is treated as deterministic truth; there is no separate forecast series and therefore no forecast-accuracy KPI or uncertainty cone - the standard set by the M5 competition is explicit probabilistic (quantile) forecasting.**

_Evidence:_ The M5 Uncertainty competition (Makridakis et al., IJF 2022) required competitors to produce 9 quantile forecasts (P50/P10-P90-style cones) for 42,840 hierarchical Walmart series, establishing probabilistic forecasting as the field standard; interval width (U-L) is the accepted uncertainty measure. The repo's base_monthly_demand is a single deterministic number per family/month with no forecast analogue. Industry benchmarks put achievable monthly MAPE for stable high-volume durables at 10-20%, and 20-35% for seasonal/promotional items, so appliances realistically sit at 15-30% MAPE.

_Implication for repo:_ Generate two correlated series per family: a forecast (what sales committed to) and an actual demand (the truth the plan is judged against), with a seeded per-family bias term (+/- a few %) plus +/-15-25% seeded noise. Render a P10/P50/P90 cone around the forecast in the dashboard and surface a forecast-accuracy (MAPE) and bias KPI. This turns the cockpit from a deterministic solver into a planning-under-uncertainty demo, which is the whole point of IBP.

_Sources:_

- Evaluating quantile forecasts in the M5 uncertainty competition (International Journal of Forecasting) (2022) — https://www.sciencedirect.com/science/article/abs/pii/S0169207022000449
- M5 Forecasting - Uncertainty (Kaggle competition) (2020) — https://www.kaggle.com/c/m5-forecasting-uncertainty
- Forecast Accuracy Benchmarking for Enterprise Planners - R4 AI (2024) — https://r4.ai/forecast-accuracy-benchmarking-enterprise-planners/
- Average Monthly National Demand Forecast Error (MAPE) - APQC Open Standards Benchmarking (2024) — https://www.apqc.org/resources/benchmarking/open-standards-benchmarking/measures/average-monthly-national-demand

**At family-level monthly buckets (thousands of units), a Normal demand distribution is the correct and comprehensible choice; Negative Binomial is only warranted at SKU/weekly or intermittent granularity.**

_Evidence:_ Unlu & Rossetti compare normal, gamma, Poisson and negative binomial for lead-time demand and note Normal is adequate when demand is continuous and aggregated; NB/gamma win only for overdispersed or intermittent (variance > mean) series. By the central limit theorem, thousands of independent appliance purchases per month sum to an approximately Normal monthly total. NB and Croston-type methods are documented as the tools for lumpy/intermittent demand - which family-monthly appliance volume is not.

_Implication for repo:_ Keep using additive Normal-shaped noise on the seasonal mean (the current rng.uniform(+/-3%) is a uniform approximation of this). If a forecast/actual split is added, draw the actual from Normal(mean=forecast, sigma=forecast x MAPE_target) rather than a uniform band, which gives a statistically honest error distribution at zero extra complexity. Do NOT add Negative Binomial machinery - it would be overkill at this aggregation and would hurt comprehensibility.

_Sources:_

- Evaluating the Lead Time Demand Distribution for (r, Q) Inventory Policies - Unlu & Rossetti (2016) — https://rossetti.uark.edu/files/2016/08/iie281.pdf
- Introduction to Intermittent Demand - Open Forecast (2024) — https://openforecast.org/2024/06/18/introduction-to-intermittent-demand/

**S&OP operates at the product-family level over monthly buckets; a 2-level hierarchy (division -> family) adds dimensionality without the comprehensibility cost of SKU-level data.**

_Evidence:_ Arkieva's hierarchical-planning framework specifies S&OP runs at 'aggregate product family level' in 'monthly buckets' over a 2-3 year horizon, with SKU-level detail deferred to a lower tactical layer (weekly, 6-12 months). ASCM/APICS frames S&OP as a 'single set of numbers' balancing supply and demand at the family level. The repo's 6 flat families are correctly scoped for an S&OP demo; the missing piece is a rollup dimension so the dashboard can show an aggregate view.

_Implication for repo:_ Add one rollup level above family - e.g. two divisions: 'Kitchen' (Refrigerators, Ranges, Dishwashers, Microwaves) and 'Laundry' (Washers, Dryers) - as a field on each family. The dashboard can then render a division-level KPI row and a family-level drilldown. Do NOT add SKUs: 6 families x 12 months is already a legible demo grid; SKU explosion would destroy the 'comprehensible' half of the brief.

_Sources:_

- Hierarchical Supply Chain Planning - S&OP to Execution - Arkieva (2023) — https://arkieva.com/blog/hierarchical-supply-chain-planning-sop-to-execution/
- Sales and Operations Planning (S&OP) - ASCM (APICS) (2024) — https://www.ascm.org/topics/sales-and-operations-planning/

**The repo's shared-bottleneck design is already textbook Theory of Constraints; the sophistication upgrade is a shared feeder/component resource (a BOM bottleneck), not more parallel lines.**

_Evidence:_ TOC's five focusing steps establish that exploiting the single bottleneck (Assembly Line A, which the three highest-margin/heaviest families compete for) is the highest-leverage planning action. The repo already encodes this: HOURS_PER_UNIT routes REF/WSH/DRY onto shared Line A and margin-priority rationing in constrain.py allocates scarce hours. NetSuite/iFactory note the weakest-link resource governs the whole chain. The realistic refinement is a shared component (e.g. a compressor or stamped-steel part consumed by multiple families) which is the more common real-world bottleneck than a second assembly line.

_Implication for repo:_ Optionally add a fifth shared resource representing a component feeder (e.g. 'RES-COMP: Compressor/Stamped-Metal Cell') with per-family hours, so two distinct bottlenecks can bind in different months - this creates a richer where's-the-constraint-this-month story. If Lavi wants to keep the model minimal, the current single-Line-A bottleneck is already a correct TOC demo; the component resource is an additive sophistication, not a fix.

_Sources:_

- Theory of Constraints (TOC) - leanproduction.com (2024) — https://www.leanproduction.com/theory-of-constraints/
- Capacity Constraints: Definition and Solutions - NetSuite (2024) — https://www.netsuite.com/portal/resource/articles/erp/capacity-constraints.shtml
- Capacity Planning: Bottleneck Analysis & Constraint Management - iFactoryApp (2024) — https://ifactoryapp.com/industries/manufacturing-plant/capacity-planning-bottleneck-analysis-constraint-management

**Realistic appliance parameters are a 4-6 week production lead time and a minimum production lot size; both are absent and both are what create the motivation to build ahead.**

_Evidence:_ Grounded practitioner sources put major-appliance manufacturing lead time at 2-12 weeks with a typical 4-6 weeks (after materials are in-house, ~3-4 weeks), with component/electronics lead times of 12-40 weeks as a separate tier. Lot sizing follows EOQ/EPQ (Economic Production Quantity = sqrt(2 x D x K / H)), with the appliance industry trending toward smaller lots. These two parameters are precisely what force a plan to produce this month for next month's demand - the mechanism that makes a multi-period plan non-trivial.

_Implication for repo:_ Add two per-family fields: production_lead_time_weeks (e.g. 4-6) and min_lot_size (e.g. 200-500 units). In the constrained plan, a family's month-M production must be decided lead-time weeks ahead, and production quantities snap up to the nearest lot. This is what makes build-ahead and backorder logic meaningful and is a prerequisite for the rolling inventory balance below.

_Sources:_

- Manufacturing Lead Times for Appliances (practitioner compilation) - MrPEasy (2024) — https://mrpeasy.com/
- Electronic Component Lead Times - SEACOMP (2024) — https://www.seacomp.com/
- Economic Order Quantity: A State-of-the-Art in the Era of Uncertainty - MDPI Sustainability (2024) — https://www.mdpi.com/2071-1050/16/14/5965

**The rolling inventory balance (Opening + Production - Demand = Closing, where each month's closing becomes next month's opening) is the defining mechanic of an S&OP supply plan and is currently missing - the repo carries one static opening_inventory_units per family with no month-over-month propagation.**

_Evidence:_ The Wallace & Stahl 'S&OP How-To Handbook' methodology (the canonical S&OP reference) builds the supply plan as a monthly projection-of-balance sheet where opening inventory + scheduled production - forecast demand = projected closing inventory, rolling forward each month; SAP and ASCM describe the S&OP output as a 'rolling operational plan' over 18-36 monthly buckets. The repo currently has opening_inventory_units as a single static scalar and computes no closing balance, so there is no inventory position to manage across the 12 months - the plan cannot show stockouts, build-ahead, or end-of-year inventory position.

_Implication for repo:_ Implement a 12-month inventory projection per family: closing[m] = max(0, opening[m] + production[m] - demand[m]); opening[m+1] = closing[m] (plus optional backorder carry if backorders are enabled). Store this as a list on each family's scenario result and render it as the cockpit's central 'inventory position over time' chart. This is the single highest-value change: it converts the demo from a one-shot capacity check into a genuine rolling S&OP plan.

_Sources:_

- What is Sales and Operations Planning (S&OP)? - SAP (rolling 18-36 month plan) (2024) — https://www.sap.com/resources/sop-sales-and-operations-planning
- Sales and Operations Planning (S&OP) - ASCM (APICS) (2024) — https://www.ascm.org/topics/sales-and-operations-planning/
- How to Make the S&OP Process More Robust (supply-demand balance mechanics) - Demand-Planning.com (2016) — https://demand-planning.com/2016/03/07/how-to-make-the-sop-process-more-robust/

**The opening inventory levels are calibrated low versus the durable-goods benchmark of ~60-90 days of supply; recalibrating them makes the numbers smell right to a practitioner.**

_Evidence:_ Grounded benchmarks: Whirlpool inventory turnover ~6.0x implies ~61 days of supply, LG Electronics ~6.2x implies ~59 days; the home-goods/housewares wholesale benchmark is 61-90 days. The repo's Refrigerators open at 4,200 units vs ~3,000/mo average demand = ~42 days; Washers 3,100 vs 2,500 = ~37 days; Microwaves 6,500 vs 4,000 = ~49 days. All are 15-30% below the 60-90 day industry norm, which a practitioner would read as 'under-stocked for a seasonal peak.'

_Implication for repo:_ Recalibrate each family's opening_inventory_units to ~60-90 days of its average monthly demand (e.g. Refrigerators ~6,000-7,500 instead of 4,200). This is a one-table change in FAMILY_TABLE and immediately makes the starting position defensible. Pair it with the rolling balance so the audience can watch days-of-supply breathe across the seasonal peak.

_Sources:_

- Whirlpool / LG inventory turnover (days of supply) - Finbox (2024) — https://finbox.com/
- Inventory Days of Supply benchmarks (home goods/housewares 73-146 days; wholesalers 61-90) - practitioner compilation (2024) — https://www.netsuite.com/portal/resource/articles/erp/capacity-constraints.shtml

**The repo's determinism story (fixed SEED = 20260714, byte-identical reruns) already follows best practice; the two finishing touches are a --seed CLI override and a seed-stamp in the output JSON, plus per-stream RNG to avoid correlated noise.**

_Evidence:_ The synthetic-data literature treats reproducibility as versioning the entire generation spec (seed, schema, rules) as an artifact; K2view and Chan (2022) emphasize that a dataset is only valid if its generation can be re-run byte-identically from a recorded seed and parameter set. The repo's fixed-seed + normalized-seasonality design already delivers this. The gap is operational: the seed is hardcoded in datagen.py rather than exposed as a CLI flag and stamped into output/comparison.json, so a reviewer cannot verify which seed produced a given dashboard without reading source.

_Implication for repo:_ Add a --seed flag to the CLI defaulting to 20260714, write {'seed': <seed>, 'generated_at': <utc>} into comparison.json, and seed a separate random.Random per noise stream (demand, forecast-error) using hashlib-derived sub-seeds so adding a new stream later cannot perturb existing outputs. Keep numpy out - the stdlib random.Random approach preserves the zero-dependency constraint.

_Sources:_

- Generation of synthetic manufacturing datasets (discrete-event simulation framework) - K.C. Chan, Taylor & Francis (2022) — https://www.tandfonline.com/doi/full/10.1080/21693277.2022.2086642
- What is Synthetic Data Generation? A Practical Guide (reproducibility as versioned artifact) - K2view (2024) — https://www.k2view.com/what-is-synthetic-data-generation/

**Open supply-chain datasets (M5, Favorita, Olist) exist for calibrating the shape and hierarchy of synthetic demo data, even though they are retail rather than manufacturing.**

_Evidence:_ M5 (Walmart, 42,840 hierarchical series, 11 aggregation levels), Corporacion Favorita (Ecuadorian grocery, ~54 stores x ~4,000 SKUs, strong seasonal/event shocks), and Olist (Brazilian e-commerce, ~100k orders with lead-time fields) are the canonical open datasets for hierarchical demand. While none is a durable-goods manufacturer, their published seasonality shapes, aggregation hierarchies, and forecast-error distributions are the right reference for making Cascade Appliances' synthetic curves believable, and M5's reproducibility suite (fixed seeds, backtest windows, MASE/WRMSSE) is a template for the repo's own determinism.

_Implication for repo:_ Use M5/Favorita seasonal-index shapes as a sanity check that the repo's SEASONAL_SHAPE curves (spring peak ~1.3, Q4 peak ~1.2-1.35, trough ~0.85) sit in a realistic envelope - they do. Optionally cite M5 in the repo README as the methodological basis for the forecast-error/uncertainty-cone feature, giving the demo a defensible academic anchor rather than invented numbers.

_Sources:_

- M5 Forecasting - Uncertainty (Walmart, 42,840 hierarchical series) - Kaggle (2020) — https://www.kaggle.com/c/m5-forecasting-uncertainty
- Corporacion Favorita Grocery Sales Forecasting - Kaggle (2017) — https://www.kaggle.com/competitions/favorita-grocery-sales-forecasting
- Brazilian E-Commerce Public Dataset by Olist - Kaggle (2018) — https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce

#### Choices for Lavi

- Forecast cone vs deterministic demand: Add a forecast-vs-actual split with a P10/P50/P90 uncertainty cone and a MAPE/bias KPI (turns the cockpit into a genuine planning-under-uncertainty demo, the M5-standard approach), OR keep demand as a single deterministic truth (simpler story, less to explain). This is the headline scope call for this dimension.
- Rolling inventory balance: Implement the 12-month Opening+Production-Demand=Closing roll-forward (the single highest-value change, makes the plan multi-period and enables stockout/build-ahead/days-of-supply views), OR keep the current single static opening-inventory scalar. Strongly recommended, but it cascades into constrain.py and the dashboard.
- Lead times + lot sizes + build-ahead: Add per-family 4-6 week production lead time and a minimum lot size so production must be committed ahead and snapped to lots (richly realistic, enables backorders and build-ahead), OR stay with instantaneous single-period production. Adds realism but complicates the rationing logic and the comprehensibility budget.
- Demand trend: Add a gentle annual growth trend (3-6%/yr) so the level slopes up across the year (more realistic multiplicative-on-trend seasonality), OR keep the flat level (simpler, the feasibility arithmetic is easier to verify by eye).
- Product hierarchy depth: Add one rollup level (Kitchen/Laundry divisions above the 6 families) for an aggregate dashboard view, OR keep the flat 6-family structure. Low-cost dimensionality gain, but another thing to render and explain.
- Shared component/BOM bottleneck: Add a fifth shared feeder resource (e.g. compressor/stamped-metal cell) so two distinct bottlenecks can bind in different months, OR keep the single Assembly-Line-A bottleneck. Adds TOC richness vs minimal-model purity.
- Opening-inventory recalibration: Restate opening_inventory_units to ~60-90 days of supply (industry norm; current levels read as under-stocked), OR keep the current values. One-table change but it shifts every downstream inventory chart.

### Dimension 5: IBP financial layer & KPIs

**Confidence:** high  |  **Findings:** 5  |  **Choices:** 4

IBP's defining move over unit-based S&OP is the "integrated reconciliation" step that dollarizes the volume plan (revenue, margin, working capital) and reconciles it bottom-up against top-down financial targets in the same monthly cycle. For capacity-allocation and product-mix decisions, managerial accounting and Theory-of-Constraints literature are unanimous that the decision-relevant metric is CONTRIBUTION margin (price minus variable cost), not gross margin — gross margin embeds arbitrarily-allocated fixed overhead and misleads rationing. The repo already computes price-minus-variable-cost but mislabels it "gross_margin" throughout. A deeper correctness issue: TOC/throughput accounting requires ranking scarce capacity by contribution PER UNIT OF THE BOTTLENECK RESOURCE (per bottleneck hour), not per unit of product — the repo ranks per unit. Standard exec KPIs the cockpit lacks (per SCOR/ASCM/OEE): perfect order, OEE, schedule attainment, inventory turns/days, NPI ramp; and the "fund-the-bottleneck" decision is currently shown only as margin-at-risk with no capital outlay, payback, or ROI to frame the investment.

#### Findings

**IBP's defining addition over S&OP is the integrated reconciliation step that dollarizes the unit/volume plan into revenue, margin, working capital and reconciles it against the financial plan in the same monthly cycle — S&OP stops at volume alignment.**

_Evidence:_ Oliver Wight (the originator of the IBP class) describes 'integrated reconciliation' as the 4th step of the 5-step monthly cycle, where demand review 'translates volume into revenue and margin,' supply review calculates 'the cost of fulfilling demand,' and the management business review consolidates 'P&L projections, revenue margin, the cost implications of plans, cash flow, and income' over a rolling 36-month horizon. They call this the point where 'S&OP truly transcends into an integrated planning process.' Multiple practitioners (o9, Metapraxis, Elisa IndustriQ) concur IBP 'dollarizes' the plan whereas S&OP is volume-centric. The repo's finance.py already does this reconciliation (supply plan -> revenue/margin/inventory value) and its own docstring cites Oliver Wight correctly.

_Implication for repo:_ The reconciliation is implemented but its framing is incomplete: the cockpit shows per-scenario revenue/margin but does NOT reconcile the bottom-up plan against an explicit financial TARGET (budget/commit), which is the heart of IBP reconciliation. Add a target/revenue-commit input per scenario and surface a 'gap-to-plan' ($ and %) line in the dashboard so the demo visibly does the volume-to-value reconciliation IBP is named for.

_Sources:_

- Transitioning from S&OP to Integrated Business Planning (2024) — https://oliverwight-eame.com/transitioning-from-sales-and-operations-planning-to-integrated-business-planning/
- What Is Integrated Business Planning? IBP Explained (o9 Solutions) (2024) — https://o9solutions.com/articles/what-is-ibp
- Integrated Business Planning: Aligning Strategy, Finance, and Operations (Elisa IndustriQ) (2024) — https://www.elisaindustriq.com/resources/blog/integrated-business-planning-aligning-strategy-finance-and-operations

**For capacity-allocation and product-mix decisions the correct metric is CONTRIBUTION margin (price minus variable cost), NOT gross margin; gross margin mis-allocates fixed overhead and produces wrong rationing calls.**

_Evidence:_ Wiss's manufacturing-operations analysis demonstrates that two products with identical 15% gross margins can have wildly different contribution margins ($60 vs $30) because fixed-cost allocation is arbitrary; it concludes 'Gross margin tells you overall profitability. Contribution margin tells you which products to prioritize... where to allocate capacity.' The principle is that fixed costs (rent, depreciation, salaried overhead) do not change with a short-run make/don't-make decision, so they are irrelevant to the choice and only variable costs should be netted. Allocating heavy fixed overhead to a product can even make a positive-contribution product look unprofitable, triggering a wrong drop decision.

_Implication for repo:_ This is a real mislabel bug, not a cosmetic one. models.py line 101-102 defines unit_margin = unit_price - unit_variable_cost, which is contribution margin per unit; yet FinanceLine.gross_margin, FinanceSummary.total_gross_margin, the 'Gross margin' dashboard label, kpi.gross_margin_kpi, and docs/03-kpi-reference.md all call it 'gross margin.' Rename the field/label/columns to 'contribution_margin' / 'Contribution Margin' throughout (models.py, finance.py, kpi.py, dashboard.py, docs). The math is already correct; only the name lies to an executive reader.

_Sources:_

- Understanding Contribution Margin in Manufacturing Operations (Wiss) (2024) — https://wiss.com/contribution-margin-manufacturing-operations/
- Contribution Margin Explained (Investopedia) (2024) — https://www.investopedia.com/terms/c/contributionmargin.asp

**Margin-priority rationing of a constrained resource MUST rank by contribution (throughput) PER UNIT OF THE BOTTLENECK RESOURCE, not by contribution per unit of product — ranking per unit mis-allocates scarce hours and lowers total throughput.**

_Evidence:_ ACCA's throughput-accounting technical article gives the canonical 4-step rule: (1) throughput per unit = selling price less direct material cost; (2) throughput return per hour of bottleneck resource = throughput per unit / time on bottleneck; (3) 'rank products in order of priority, starting with the product that generates the highest return per hour first'; (4) allocate bottleneck hours in ranked order. It warns a product with the highest per-unit profit can be the WRONG priority if it consumes more bottleneck time than a lower-margin but faster product. The Emerald Insight academic paper confirms TOC 'decides product throughput per unit of working time at the bottleneck.' This is the standard CIMA/ACCA examinable method.

_Implication for repo:_ constrain.py line 86 rations by `sorted(users, key=lambda f: f.unit_margin, reverse=True)` — contribution per UNIT. The data needed for the correct ranking already exists (family.resource_hours_per_unit[resource.id]); change the sort key to `f.unit_margin / f.resource_hours_per_unit[resource.id]` (contribution per bottleneck hour) when the resource is the binding constraint. In the current seed this happens not to flip the Refrigerators>Washers>Dryers order, so the demo output stays stable, but the engine becomes methodologically defensible and a reviewer cannot debunk it. Flag the change in implementation-notes.md as a TOC correction.

_Sources:_

- Throughput accounting and the theory of constraints, part 2 (ACCA Global) (2023) — https://www.accaglobal.com/gb/en/student/exam-support-resources/fundamentals-exams-study-resources/f5/technical-articles/throughput-constraints2.html
- An improved theory of constraints (Emerald Insight) (2008) — https://www.emerald.com/insight/content/doi/10.1108/18347640810913816/full/html

**The KPI set executives actually track spans five SCOR performance attributes (Reliability, Responsiveness, Agility, Cost, Asset Management Efficiency); the cockpit currently covers Reliability partially and Cost, but omits standard Level-1 metrics: perfect order, OEE, schedule attainment, inventory turns/days, and NPI ramp.**

_Evidence:_ SCOR (maintained by ASCM, formerly APICS Supply Chain Council) defines Level-1 metrics under five attributes: Reliability = Perfect Order Fulfillment + Fill Rate; Responsiveness = Order Fulfillment Cycle Time; Agility = upside/downside supply chain adaptability; Cost = Total SCM Cost + COGS; Asset Management Efficiency = Inventory Turns + Cash-to-Cycle + Return on SC Fixed Assets. OEE.com and the Lean Enterprise Institute define OEE = Availability x Performance x Quality (world-class ~85%, 60% typical). Schedule attainment/adherence is called out as complementary to OEE. The repo's kpi.py currently exposes: fill_rate, gross_margin (mislabeled CM), revenue, inventory_value, bottleneck util, lost_margin, lost_revenue, upside_value_unlocked.

_Implication for repo:_ Add at least: (a) Perfect Order % — decompose fill rate into on-time + complete + damage-free factors (parameterized) to show the Reliability gap a simple fill rate hides; (b) OEE for the bottleneck Assembly Line A (A x P x Q inputs in datagen); (c) Schedule Attainment = actual_shipped / scheduled for the month; (d) Inventory Turns = COGS / avg inventory value and Inventory Days = 365 / turns (the repo already has ending inventory value, so turns is one derived line); (e) NPI ramp % for a designated new family. Each is a single formula; gate which ones render to avoid dashboard clutter.

_Sources:_

- SCOR Model - Supply Chain Operations Reference (CIPS) (2024) — https://www.cips.org/intelligence-hub/procurement/kpis/scor-model
- What Is OEE (Overall Equipment Effectiveness)? (OEE.com) (2024) — https://www.oee.com/
- Overall Equipment Effectiveness (Lean Enterprise Institute) (2024) — https://www.lean.org/lexicon-terms/overall-equipment-effectiveness/
- SCOR Model: Complete Guide (ShipBob) (2024) — https://www.shipbob.com/blog/scor-model/

**The 'fund-the-bottleneck' decision should be framed financially with a capital outlay plus annual recovered margin yielding payback period and ROI; the cockpit currently shows only the annual margin-at-risk ($531,728) with no investment, payback, or return, so the investment case is invisible.**

_Evidence:_ Nucleus Research's investment-justification framework maps metrics to questions: 'Is it worth it?' -> ROI (average annual net benefit / initial cost); 'How long to recover the outlay?' -> Payback Period (intuitive + a risk indicator). It argues NPV is weak for capacity projects with ongoing rather than terminal benefits, and IRR is manipulable. For a debottlenecking project the numerator is the incremental annual benefit (the throughput/margin recovered) and the denominator is the initial capital outlay. The repo already computes the numerator (upside_value_unlocked = upside margin - constrained margin = $531,728); it has no denominator.

_Implication for repo:_ Model the bottleneck investment explicitly: add an `investment_cost` input for the Assembly Line A expansion (e.g. capex to lift installed hours), then derive Payback = investment_cost / annual_recovered_margin and ROI = (annual_recovered_margin - annualized_cost) / investment_cost. Surface these next to upside_value_unlocked so the 'fund the bottleneck' call has a financial frame. Keep it simple (single-period cash flow); an NPV/IRR treatment is optional and probably over-engineers a demo. This converts the cockpit from 'here is the margin at risk' to 'here is the investment case to recover it.'

_Sources:_

- Everything to Know About ROI, TCO, NPV, and Payback (Nucleus Research) (2023) — https://nucleusresearch.com/everything-to-know-about-roi-tco-npv-and-payback/
- Return on Investment (ROI) in Manufacturing: Formula & Use (Symestic) (2024) — https://www.symestic.com/en-us/what-is/return-on-investment

#### Choices for Lavi

- Rename or augment: should the cockpit relabel 'gross margin' -> 'contribution margin' everywhere (correct, but it is the field name in FinanceLine and ripples through tests/docs), OR ALSO compute a true gross margin line (with allocated fixed overhead) so the exec P&L reconciliation shows both? Adding true gross margin means introducing a fixed-overhead allocation basis, which reintroduces the very arbitrariness IBP tries to avoid — my recommendation is rename only, but it is Lavi's scope call.
- Rationing method: switch the sort key to contribution-per-bottleneck-hour (TOC-correct, defensible to any SC reviewer) or keep per-unit contribution margin (simpler to explain on a demo, unchanged output on current seed)? This is a realism-vs-comprehensibility tradeoff — the correct method is harder to narrate but cannot be debunked.
- Which of the missing exec KPIs to actually render: all five (perfect order, OEE, schedule attainment, inventory turns/days, NPI ramp) gives SCOR coverage but risks dashboard clutter for a single-period demo; a minimal set (inventory turns + OEE) keeps the cockpit readable. Lavi decides how comprehensive the KPI tile row should be.
- Fund-the-bottleneck frame: model the capital outlay and compute payback + ROI (turns the constrained-vs-upside gap into an investment case), or leave it as margin-at-risk only? Adding it needs one new input (investment_cost) and changes the cockpit narrative from 'what we lose' to 'whether to invest' — a scope decision about how far the demo goes toward capital budgeting.

### Dimension 6: Real S&OP tool benchmark

**Confidence:** medium  |  **Findings:** 7  |  **Choices:** 5

The six leading S&OP/IBP tools (Kinaxis, o9, SAP IBP, Anaplan, Blue Yonder, OMP) converge on a near-identical cockpit pattern: an executive KPI tile row on top, side-by-side what-if scenario comparison as the core interaction, capacity/utilization with threshold markers, financial reconciliation (revenue/margin/working capital) that monetizes the supply plan, and drill-down from global to SKU. They all run on proprietary optimization engines (LP/MIP solvers, o9's Enterprise Knowledge Graph, ML demand forecasting) and are, by design, black boxes. That black-box nature is precisely the opening for a stdlib-only cockpit whose arithmetic is fully auditable: the realistic scope ceiling is deterministic, multi-period, multi-scenario planning with inspectable heuristics — anything requiring a real solver, ML, a graph data model, or live multi-user collaboration crosses from portfolio piece into toy. The honest, distinctive framing is "transparent white-box cockpit," not "optimizer."

#### Findings

**Side-by-side scenario comparison with what-if simulation is the universal core interaction of every leading S&OP/IBP cockpit — not a tabbed one-at-a-time view.**

_Evidence:_ Kinaxis markets 'unlimited, instantaneous what-if scenario simulations' for S&OP (fetched from its S&OP solution page). o9's 'Advanced Scenario Planning Engine' lets teams 'simulate alternative futures and compare scenarios side by side.' SAP IBP's Planner Workspaces and Inventory Analysis app support creating and comparing multiple versions. Anaplan offers 'what-if' scenarios with side-by-side comparison. Blue Yonder's 'War Game' engine shows impacts on P&L, cash flow, and service levels 'side-by-side.' OMP Unison Planning emphasizes 'assess scenario trade-offs.' The current repo dashboard uses scenario TABS (one scenario visible at a time per chart) — orthogonal to the dominant vendor pattern.

_Implication for repo:_ Add a side-by-side overlay mode to the capacity-utilization and demand-vs-supply charts in src/sop_integrated_planning/dashboard.py (currently one-scenario tabs via capScenario/gapScenario). A grouped/overlaid bar chart showing BASE/UPSIDE/CONSTRAINED together — or at minimum a fourth 'All scenarios' tab — matches the dominant cockpit language and makes the upside-value-unlocked delta visually immediate instead of requiring the viewer to mentally subtract across tabs.

_Sources:_

- Kinaxis — Transform S&OP with seamless, risk-free planning (2026) — https://www.kinaxis.com/en/solutions/sales-and-operations-planning
- o9 Solutions — Integrated Business Planning (Advanced Scenario Planning Engine) (2026) — https://o9solutions.com/solutions/integrated-business-planning
- Blue Yonder — What is Blue Yonder Integrated Business Planning (War Game / Boardroom Dashboard) (2026) — https://info.blueyonder.com/supply-chain-planning/what-is-blue-yonder-integrated-business-planning
- SAP IBP Help — Scenario Planning / Planner Workspaces (2026) — https://help.sap.com/docs/SAP_INTEGRATED_BUSINESS_PLANNING/feae3cea3cc549aaa9d9de7d363a83e6/ea818511561e4b86ab461c37a0fe185d.html

**The IBCS/ISO 24896 visual standard is the de-facto notation for professional S&OP dashboards: solid fill = actuals, hollow/outlined = plan, hatched = forecast, grey = prior period, and color (green/red) is reserved strictly for variance from a reference — not used to identify scenarios.**

_Evidence:_ The IBCS Institute (now backed by ISO 24896 'Notation for business reporting') prescribes: solid black for actuals, outline for plan/budget, hatched for forecast, grey for previous year; 'colors should be reserved for more important things' i.e. deviations only; bars for structural comparison, columns/lines for time series, waterfalls for variance bridges; synchronize axes across small multiples; label data directly instead of using legends. Zebra BI's implementation guide corroborates these exact rules. This is the visual grammar practitioners trained on APICS/Oliver Wight IBP expect.

_Implication for repo:_ The current dashboard uses per-scenario solid colors (CSS var --s1 etc.) to identify scenarios, which is the opposite of IBCS convention. A credible 'analyst-grade' option: reserve a single accent color for variance-from-BASE (green = upside gained, red = margin at risk), render BASE as the solid reference, UPSIDE/CONSTRAINED as hollow/hatched variants, and add a waterfall chart for the upside-value-unlocked bridge (CONSTRAINED margin → +investment recovery → UPSIDE margin). This is a genuine aesthetics-vs-convention tradeoff for the owner.

_Sources:_

- IBCS Institute — Standards (Notation + Composition, aligned with ISO 24896) (2026) — https://www.ibcs.com/standards/
- Zebra BI — Achieve Consistent Reporting with IBCS (concrete notation rules) (2026) — https://zebrabi.com/ibcs/

**A variance/delta-from-baseline view is the single most common executive frame across vendor cockpits — the answer to 'so what changed?' — and the current repo has no explicit variance view.**

_Evidence:_ Blue Yonder's Boardroom Dashboard centers on executive KPIs with drill-down; its War Game surfaces scenario impacts 'side-by-side' on P&L, cash, service levels — i.e., deltas. Anaplan's scenario planning is built around 'real-time impact modeling' and side-by-side comparison. o9's scenario engine compares alternatives. The repo's KPI catalog already computes 'upside value unlocked (Δ gross margin UPSIDE − CONSTRAINED)' and 'margin at risk', but the dashboard surfaces these only as standalone tiles, not as a structured variance/bridge view against the BASE reference plan.

_Implication for repo:_ Add a 'variance from BASE' card to dashboard.py: a small-multiples or table view showing each scenario's revenue/margin/fill-rate as an absolute and percentage delta against BASE, color-coded per IBCS. This directly exercises the already-computed upside-value-unlocked and margin-at-risk KPIs and is the frame an executive reviewer expects first.

_Sources:_

- Blue Yonder — Boardroom Dashboard + War Game (executive KPIs, side-by-side P&L/cash/service impact) (2026) — https://info.blueyonder.com/supply-chain-planning/what-is-blue-yonder-integrated-business-planning
- Anaplan — Leveraging Scenario Planning and Analysis (side-by-side comparison) (2026) — https://bedfordconsulting.com/how-can-you-leverage-anaplan-for-effective-scenario-planning-and-analysis

**Real S&OP/IBP engines are built on optimization solvers (LP/MIP) and ML/graph data models — not deterministic heuristic arithmetic — which is the hard scope ceiling for a stdlib-only repo.**

_Evidence:_ Peer-reviewed and practitioner OR literature confirms production supply-chain planning uses mixed-integer linear programming (MDPI Systems 2025, Vicente et al.; Maravelias, CMU, on MIP for supply-chain planning coordination of materials/information/financial flows; AnyLogistix: 'linear and mixed-integer programming are commonly used methods'). o9 markets an AI 'Enterprise Knowledge Graph' (graph data model + optimization); vendors do not disclose solvers but all run optimization under the hood. Python's stdlib has no LP/MIP solver and no array/ML library — so any claim of 'optimal' plans, probabilistic forecasting, or graph-based planning in this repo would be a toy reimplementation rather than the real thing.

_Implication for repo:_ Hard-guardrail the language: the margin-priority rule in constrain.py is a GREEDY HEURISTIC, not an optimization — label it precisely as 'greedy margin-priority rationing' everywhere (README, dashboard exec-takeaway, kpi-reference) so the repo never overclaims into toy territory. The distinctive positioning is 'fully auditable deterministic cockpit,' explicitly contrasted with vendor black-box solvers. Do NOT add an 'optimal plan' claim without a real solver (which would break stdlib-only).

_Sources:_

- Optimizing Supply Chain Inventory: A Mixed Integer Linear Programming Approach (MDPI Systems) (2025) — https://www.mdpi.com/2079-9454/13/1/33
- Christos Maravelias (CMU) — Mixed-integer programming methods for supply chain planning (2011) — https://cepac.cheme.cmu.edu/pasi2011/library/maravelias/PASI2011-Maravelias.pdf
- o9 Solutions — Enterprise Knowledge Graph / Digital Brain for IBP (2026) — https://o9solutions.com/solutions/integrated-business-planning/digital-ibp

**Rough-Cut Capacity Planning (the repo's capacity engine) is openly criticized by practitioners as a 'snapshot' that produces feasible-but-not-optimal plans — which is a STRENGTH for the cockpit's honest positioning if framed correctly, and a liability if the repo implies it is more.**

_Evidence:_ River Logic argues 'It's Time to Move Beyond Rough Cut Capacity Planning' — that RCCP is outdated, produces feasible but not optimal plans, and S&OP should focus on profit optimization. RELEX describes RCCP as a 'snapshot view.' This critique exactly delimits what RCCP legitimately claims: feasibility and bottleneck visibility, not optimality. The repo already leans on this honestly (capacity.py is framed as 'standard MRP-II/APICS feasibility check').

_Implication for repo:_ Turn the acknowledged RCCP limitation into an explicit, sourced design note in implementation-notes.md / README: cite that RCCP is a deliberate, transparent feasibility-and-bottleneck lens (per the practitioner critique), and that the cockpit exposes the gap rather than hiding it in an optimizer. This converts a would-be weakness into the documented rationale for the white-box approach.

_Sources:_

- River Logic — It's Time to Move Beyond Rough Cut Capacity Planning (2026) — https://download.riverlogic.com/blog/its-time-to-move-beyond-rough-cut-capacity-planning
- RELEX Solutions — Rough-cut capacity planning ('snapshot view') (2026) — https://www.relexsolutions.com/resources/rough-cut-capacity-planning/

**Drill-down from an executive summary to family/SKU/resource/month granularity is a baseline expectation of every vendor cockpit, and the repo's dashboard currently has no drill path — every chart is a flat leaf view.**

_Evidence:_ Blue Yonder's Boardroom Dashboard: leaders 'drill from a global summary to a regional or product-level issue within a few clicks.' SAP IBP Planner Workspaces and Anaplan connected planning are built on the same hierarchical drill model. The repo's dashboard renders fixed leaf views: a per-resource capacity chart, a monthly gap chart, and a family reconciliation table, with no expand/collapse or summary-to-detail navigation.

_Implication for repo:_ Add a lightweight drill affordance in dashboard.py using only vanilla JS: a top 'executive summary' card (totals) where clicking a family/resource row expands to reveal that row's monthly breakdown — reusing data already embedded in the DATA JSON blob. This is achievable stdlib-only (it is DOM toggle logic, no new computation) and closes the most visible gap versus vendor cockpits.

_Sources:_

- Blue Yonder — Boardroom Dashboard drill-down (global to regional/product-level) (2026) — https://info.blueyonder.com/supply-chain-planning/what-is-blue-yonder-integrated-business-planning
- SAP IBP — Planner Workspaces (drill-down analysis) (2026) — https://help.sap.com/docs/SAP_INTEGRATED_BUSINESS_PLANNING/feae3cea3cc549aaa9d9de7d363a83e6/ea818511561e4b86ab461c37a0fe185d.html

**Kinaxis, o9, SAP IBP, Blue Yonder and OMP are all positioned as Leaders in the Gartner Magic Quadrant for Supply Chain Planning Solutions; Kinaxis is cited highest on Ability to Execute and has been a Leader eleven consecutive times. This is the competitive set the cockpit is implicitly measured against.**

_Evidence:_ Gartner split the 2026 Magic Quadrant into Process Industries and Discrete Industries reports; Kinaxis is a Leader in both, highest on Ability to Execute, and has been recognized as a Leader eleven consecutive times (press release). The full Gartner report (paywalled) evaluates o9, SAP IBP, Blue Yonder, OMP and others against the same criteria set. This establishes that 'S&OP cockpit' is a mature, crowded category where a demo project's value cannot be feature-parity — it must be a differentiated angle.

_Implication for repo:_ Make the differentiation explicit in the README's opening positioning: name the category (Gartner MQ Leaders: Kinaxis/o9/SAP IBP/Blue Yonder/OMP) and state precisely why this repo exists alongside them — zero-install stdlib reproducibility + fully auditable arithmetic (their black box is our white box). A portfolio piece that does not position itself against the real market reads as naive; one that names the giants and picks a different axis of value reads as informed.

_Sources:_

- BusinessWire — Kinaxis Recognized as a Leader in the 2026 Gartner Magic Quadrant Reports (11 consecutive times) (2026) — https://www.businesswire.com/news/home/20260323129357/en/Kinaxis-Recognized-as-a-Leader-in-the-2026-Gartner-Magic-Quadrant-Reports-for-Supply-Chain-Planning
- Gartner — Magic Quadrant for Supply Chain Planning Solutions (official report) (2026) — https://www.gartner.com/en/documents/5374263

#### Choices for Lavi

- Side-by-side vs tabs: adopt an overlaid/grouped 'all scenarios' view for the capacity and gap charts (matches every vendor) or keep the cleaner one-scenario tabs (current). This is a comprehensibility-vs-vendor-conformance tradeoff — your call on which audience (recruiter skimming vs practitioner evaluating) you optimize for.
- IBCS notation adoption: fully adopt the solid/hollow/hatched + variance-color convention (reads as analyst-grade / Oliver-Wight-trained) or keep the current modern colored design (prettier, less conventional). You cannot fully serve both — IBCS reserves color for variance, the current design uses color to identify scenarios.
- Realism vs honesty on the scope ceiling: keep the clean no-backorder, single-pass, greedy-rationing model and lean into 'transparent heuristic cockpit' (honest, distinctive, defensible), OR add backorder carry + build-ahead + lot-sizing for more realism (risks looking like a toy reimplementation of real optimizers unless executed very carefully, and edges toward needing a real solver). This is the core decision that determines whether the piece is a crisp portfolio artifact or an ambitious-but-flawed mini-ERP.
- Variance/waterfall view: invest in a dedicated 'delta from BASE' card with a waterfall bridge (the universal executive frame) or treat the existing KPI tiles as sufficient. Adds meaningful dashboard surface area but is more work in pure inline SVG.
- Positioning voice: should the README explicitly name and contrast against Kinaxis/o9/SAP IBP (confident, informed, slightly provocative) or position more quietly as a 'learning cockpit' (humbler, safer)? The former stands out more but invites direct comparison; the latter avoids a fight the repo cannot win on features.


## Full source count

- 105 unique sources across all dimensions.
