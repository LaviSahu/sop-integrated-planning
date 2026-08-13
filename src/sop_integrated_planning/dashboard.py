"""
dashboard.py — the self-contained HTML decision cockpit.

`build_context(...)` assembles the exact JSON-serializable dict the
dashboard's `<script>const DATA = {...}</script>` blob embeds: the KPI
comparison tiles, per-resource capacity utilization (with the 100% RCCP
line) for all three scenarios, the monthly demand-vs-shipped gap per
scenario, the family-level financial reconciliation table, and a
computed exec-takeaway callout built from the actual numbers.

`render_dashboard(context, out_path)` renders a single, zero-CDN
`output/dashboard.html` — inline CSS (dual theme), vanilla JS, inline
SVG — following DESIGN.md exactly. The context JSON is embedded once as
`const DATA = {...}` and every section is drawn client-side by a small
pure JS function, so the renderer never recomputes anything.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from . import capacity as capacity_mod
from . import constrain as constrain_mod
from . import demand as demand_mod
from . import finance as finance_mod
from .models import (
    Family,
    FinanceLine,
    FinanceSummary,
    Kpi,
    Resource,
    ResourceLoad,
    ScenarioId,
    SupplyLine,
    jsonable,
)

# Scenarios that apply each family's upside_uplift_pct on top of base demand.
_UPLIFT_SCENARIOS = {ScenarioId.UPSIDE, ScenarioId.CONSTRAINED}

_MONTH_NAMES = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]

_SCENARIOS_IN_ORDER = [ScenarioId.BASE, ScenarioId.UPSIDE, ScenarioId.CONSTRAINED]


def _capacity_series(loads: list[ResourceLoad], resources: list[Resource]) -> dict:
    by_resource: dict[str, list[dict]] = {r.id: [] for r in resources}
    for ld in sorted(loads, key=lambda x: (x.resource_id, x.month)):
        by_resource[ld.resource_id].append(
            {
                "month": ld.month,
                "load_hours": ld.load_hours,
                "available_hours": ld.available_hours,
                "utilization_pct": ld.utilization_pct,
            }
        )
    peaks = capacity_mod.peak_utilization_by_resource(loads)
    return {
        "by_resource": by_resource,
        "peak_utilization_pct": {rid: round(v, 2) for rid, v in peaks.items()},
    }


def _scenario_monthly_totals(supply_lines: list[SupplyLine]) -> list[dict]:
    """Total demand/produced/shipped/unmet across all families, per month."""
    totals: dict[int, dict[str, float]] = {
        m: {"demand": 0.0, "produced": 0.0, "shipped": 0.0, "unmet": 0.0} for m in range(1, 13)
    }
    for sl in supply_lines:
        t = totals[sl.month]
        t["demand"] += sl.demand_units
        t["produced"] += sl.produced_units
        t["shipped"] += sl.shipped_units
        t["unmet"] += sl.unmet_units
    return [
        {
            "month": m,
            "month_name": _MONTH_NAMES[m - 1],
            "demand": round(totals[m]["demand"], 1),
            "produced": round(totals[m]["produced"], 1),
            "shipped": round(totals[m]["shipped"], 1),
            "unmet": round(totals[m]["unmet"], 1),
        }
        for m in range(1, 13)
    ]


def _family_reconciliation_rows(
    families: list[Family],
    supply_lines: list[SupplyLine],
    finance_lines: list[FinanceLine],
) -> list[dict]:
    gm_by_family = finance_mod.gross_margin_by_family(finance_lines)
    lm_by_family = finance_mod.lost_margin_by_family(finance_lines)
    rows = []
    for family in families:
        fam_supply = [s for s in supply_lines if s.family_id == family.id]
        fam_finance = [f for f in finance_lines if f.family_id == family.id]
        total_demand = sum(s.demand_units for s in fam_supply)
        total_shipped = sum(s.shipped_units for s in fam_supply)
        total_unmet = sum(s.unmet_units for s in fam_supply)
        december = next((f for f in fam_finance if f.month == 12), None)
        rows.append(
            {
                "family_id": family.id,
                "family_name": family.name,
                "unit_margin": family.unit_margin,
                "demand_units": round(total_demand, 1),
                "shipped_units": round(total_shipped, 1),
                "unmet_units": round(total_unmet, 1),
                "fill_rate_pct": round((total_shipped / total_demand * 100.0) if total_demand > 0 else 100.0, 1),
                "revenue": round(sum(f.revenue for f in fam_finance), 2),
                "gross_margin": gm_by_family.get(family.id, 0.0),
                "lost_margin": lm_by_family.get(family.id, 0.0),
                "ending_inventory_value": december.inventory_value if december else 0.0,
            }
        )
    return rows


def _provenance(
    scenario: ScenarioId,
    families: list[Family],
    resources: list[Resource],
    loads: list[ResourceLoad],
    supply_lines: list[SupplyLine],
    finance_lines: list[FinanceLine],
) -> dict[str, dict[str, dict]]:
    """
    Per (family, month): the full Demand -> Capacity -> Rationing -> Supply ->
    Financials trail for this scenario, sourced from the same objects the engine
    already computed. Mirrors mockups/build_data.py::_provenance exactly so the
    built dashboard and the golden-fixture mockups/data.js agree.

    Nothing here is a second calculation of the outcome: the rationing decision
    comes from constrain._allowed_units_this_month (the authoritative rule), and
    the supply/finance rows come straight off the engine's own SupplyLine /
    FinanceLine objects.
    """
    resources_by_id = {r.id: r for r in resources}
    demand_lines = demand_mod.build_demand_plan(families, scenario)
    demand_by_fm = demand_mod.demand_by_family_month(demand_lines)
    load_by_rm = capacity_mod.load_hours_by_resource_month(loads)
    load_lookup = {(ld.resource_id, ld.month): ld for ld in loads}
    supply_lookup = {(sl.family_id, sl.month): sl for sl in supply_lines}
    finance_lookup = {(fl.family_id, fl.month): fl for fl in finance_lines}
    allowed_by_month = {
        m: constrain_mod._allowed_units_this_month(m, families, resources, demand_by_fm, load_by_rm, scenario)
        for m in range(1, 13)
    }

    out: dict[str, dict] = {}
    for family in families:
        resource_ids = [rid for rid, hpu in family.resource_hours_per_unit.items() if hpu > 0.0]
        months_out: dict[str, dict] = {}
        for month in range(1, 13):
            demand_units = demand_by_fm.get((family.id, month), 0.0)
            uplift_applied = scenario in _UPLIFT_SCENARIOS
            allowed = allowed_by_month[month]

            capacity_rows = []
            rationing_rows = []
            for rid in resource_ids:
                resource = resources_by_id[rid]
                ld = load_lookup[(rid, month)]
                hours_per_unit = family.resource_hours_per_unit[rid]
                capacity_rows.append({
                    "resource_id": rid,
                    "load_hours": ld.load_hours,
                    "available_hours": ld.available_hours,
                    "utilization_pct": ld.utilization_pct,
                    "is_bottleneck": ld.is_bottleneck,
                    "hours_per_unit": hours_per_unit,
                })

                effective_hours = constrain_mod.effective_capacity_hours(scenario, resource, ld.load_hours)
                constrained = ld.load_hours > effective_hours + 1e-9
                users = sorted(
                    (f for f in families if f.resource_hours_per_unit.get(rid, 0.0) > 0.0),
                    key=lambda f: f.unit_margin, reverse=True,
                )
                cumulative_before = 0.0
                row = None
                for i, u in enumerate(users, start=1):
                    u_hpu = u.resource_hours_per_unit[rid]
                    u_allowed_units = allowed[(u.id, rid)]
                    u_granted_hours = u_allowed_units * u_hpu
                    if u.id == family.id:
                        wanted_hours = demand_by_fm.get((u.id, month), 0.0) * u_hpu
                        remaining_before = max(0.0, effective_hours - cumulative_before)
                        remaining_after = max(0.0, remaining_before - u_granted_hours)
                        row = {
                            "resource_id": rid,
                            "constrained": constrained,
                            "rank": i,
                            "n_users": len(users),
                            "unit_margin": round(u.unit_margin, 2),
                            "wanted_hours": round(wanted_hours, 2),
                            "remaining_before_hours": round(remaining_before, 2),
                            "granted_hours": round(u_granted_hours, 2),
                            "remaining_after_hours": round(remaining_after, 2),
                            "allowed_units": round(u_allowed_units, 2),
                        }
                    cumulative_before += u_granted_hours
                rationing_rows.append(row)

            sl = supply_lookup[(family.id, month)]
            fl = finance_lookup[(family.id, month)]

            months_out[str(month)] = {
                "demand": {
                    "base_units": family.base_monthly_demand[month - 1],
                    "uplift_pct": family.upside_uplift_pct if uplift_applied else 0.0,
                    "uplift_applied": uplift_applied,
                    "demand_units": round(demand_units, 2),
                },
                "capacity": capacity_rows,
                "rationing": rationing_rows,
                "supply": jsonable(sl),
                "financials": {
                    **jsonable(fl),
                    "unit_price": family.unit_price,
                    "unit_variable_cost": family.unit_variable_cost,
                    "unit_margin": family.unit_margin,
                },
            }
        out[family.id] = months_out
    return out


def build_context(
    families: list[Family],
    resources: list[Resource],
    loads_by_scenario: dict[ScenarioId, list[ResourceLoad]],
    supply_by_scenario: dict[ScenarioId, list[SupplyLine]],
    finance_lines_by_scenario: dict[ScenarioId, list[FinanceLine]],
    summary_by_scenario: dict[ScenarioId, FinanceSummary],
    kpis: dict[str, Kpi],
    generated_at: str,
) -> dict:
    """
    Assemble everything the dashboard needs into one JSON-serializable
    dict. This is the contract between the engine and the renderer —
    designed so the renderer never recomputes anything, only formats
    what's here.
    """
    scenarios_ctx: dict[str, dict] = {}
    provenance_by_scenario: dict[str, dict] = {}
    for scenario in _SCENARIOS_IN_ORDER:
        summary = summary_by_scenario[scenario]
        supply_lines = supply_by_scenario[scenario]
        finance_lines = finance_lines_by_scenario[scenario]

        # Monthly revenue / margin / lost margin / lost revenue, summed across
        # families — matches mockups/build_data.py so the built dashboard and
        # the golden fixture agree.
        by_month: dict[int, dict[str, float]] = defaultdict(
            lambda: {"revenue": 0.0, "gross_margin": 0.0, "lost_revenue": 0.0, "lost_margin": 0.0}
        )
        for fl in finance_lines:
            bucket = by_month[fl.month]
            bucket["revenue"] += fl.revenue
            bucket["gross_margin"] += fl.gross_margin
            bucket["lost_revenue"] += fl.lost_revenue
            bucket["lost_margin"] += fl.lost_margin

        monthly = []
        for row in _scenario_monthly_totals(supply_lines):
            m = row["month"]
            fin = by_month[m]
            monthly.append({
                "month": m,
                "name": row["month_name"],
                "demand": round(row["demand"], 1),
                "produced": round(row["produced"], 1),
                "shipped": round(row["shipped"], 1),
                "unmet": round(row["unmet"], 1),
                "revenue": round(fin["revenue"], 2),
                "gross_margin": round(fin["gross_margin"], 2),
                "lost_revenue": round(fin["lost_revenue"], 2),
                "lost_margin": round(fin["lost_margin"], 2),
            })

        scenarios_ctx[scenario.value] = {
            "id": scenario.value,
            "summary": jsonable(summary),
            "capacity": _capacity_series(loads_by_scenario[scenario], resources),
            "monthly_totals": _scenario_monthly_totals(supply_lines),
            "monthly": monthly,
            "utilization": {
                rid: [
                    {
                        "month": r["month"],
                        "load_hours": r["load_hours"],
                        "available_hours": r["available_hours"],
                        "utilization_pct": r["utilization_pct"],
                    }
                    for r in rows
                ]
                for rid, rows in _capacity_series(loads_by_scenario[scenario], resources)["by_resource"].items()
            },
            "reconciliation": _family_reconciliation_rows(families, supply_lines, finance_lines),
        }
        provenance_by_scenario[scenario.value] = _provenance(
            scenario, families, resources, loads_by_scenario[scenario], supply_lines, finance_lines
        )

    bottleneck_resource_id = capacity_mod.binding_resource(loads_by_scenario[ScenarioId.UPSIDE])
    resources_by_id = {r.id: r for r in resources}
    bottleneck_ctx = None
    if bottleneck_resource_id is not None:
        peak_load = max(
            (ld for ld in loads_by_scenario[ScenarioId.UPSIDE] if ld.resource_id == bottleneck_resource_id),
            key=lambda ld: ld.utilization_pct,
        )
        bottleneck_ctx = {
            "resource_id": bottleneck_resource_id,
            "resource_name": resources_by_id[bottleneck_resource_id].name,
            "month": peak_load.month,
            "month_name": _MONTH_NAMES[peak_load.month - 1],
            "utilization_pct": peak_load.utilization_pct,
        }

    return {
        "generated_at": generated_at,
        "company": "Cascade Appliances",
        "month_names": _MONTH_NAMES,
        "kpis": {key: jsonable(k) for key, k in kpis.items()},
        "resources": [jsonable(r) for r in resources],
        "families": [jsonable(f) for f in families],
        "scenarios": scenarios_ctx,
        "provenance": provenance_by_scenario,
        "bottleneck": bottleneck_ctx,
    }


# --------------------------------------------------------------------------
# The dashboard template. Built with a __DATA_JSON__ sentinel (not str.format)
# so every literal { } in the CSS/JS stays literal. The context JSON is
# embedded once; </ is escaped to <\/ so an embedded string can never close
# the <script> element early.
# --------------------------------------------------------------------------

_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>S&amp;OP Integrated Planning — Cascade Appliances</title>
<style>
/* =============================================================================
   tokens.css — IBCS-style S&OP planning-cockpit design tokens
   =============================================================================
   DARK-PRIMARY REWRITE (2026-08-12). This file previously shipped
   light-primary, inverted from dark reference screenshots — backwards for a
   cockpit meant to sit open on a screen for hours. Flipped: dark is now the
   default appearance, light is an explicit opt-in override (see the
   [data-theme="light"] block near the end). Structure and the `sop-` prefix
   are unchanged from the previous version.

   Grounded in 4 reference screenshots, referenced below by short id:
     A = SCR-20260805-tadk.png — cross-edition "moat" network + the
         TRANSFER CONFIDENCE legend (line thickness = confidence tier,
         dashed = experimental / low confidence)
     B = SCR-20260805-smhs.png — three-lens canvas: KPI tile row, KPI
         Health status-dot list, UOKG Explain decomposition drawer,
         narrative rail
     C = SCR-20260805-syiu.png — 4-agent verdict cards + confidence chips
     D = SCR-20260805-slit.png — "how this number was produced" provenance
         modal + narrative rail with a bordered callout box

   RESTRAINED HUE POLICY — why this palette is short: across A/B/C/D the
   source deck uses 6+ decorative hues (A alone colors five edition nodes
   orange/blue/green/purple/amber purely for visual variety, with no data
   meaning tied to the hue itself — that is deck styling, not notation). A
   planning cockpit is read for numbers under time pressure, so hue is
   budgeted to exactly 5 slots: one BRAND accent (identity/navigation only,
   never a data series) plus four SEMANTIC colors — good / bad / warn /
   info. Every other colored element in the screenshots (edition badges,
   agent-card left borders, network-node rings) is reproduced here as
   NEUTRAL INK instead, distinguished by weight, fill style, or line
   pattern rather than hue. Enforced token-by-token below, not just stated
   here — every color token's comment says which of the 5 slots it fills.

   NO GLOW: A's node rings and B's purple-glow "focused" KPI tile both use
   a soft, blurred, tinted box-shadow — decorative "sci-fi product demo"
   glow. Dropped on purpose: it doesn't export to PDF/print predictably,
   and it opens a second, non-semantic color channel that competes with
   the good/bad/warn/info signal a reader actually needs to trust. Depth
   instead comes from --sop-color-surface elevation plus a 1px hairline
   border; where a shadow exists at all (modal separation, focus ring) it
   is small and 0-to-2px blur — never a bloom.

   Every token is commented "from X.png: ..." (directly observed) or
   "derived: ..." (no direct screenshot evidence — inferred from IBCS
   convention or built for internal consistency). Nothing is invented
   without a comment saying so. Still lives in mockups/ as a DESIGN
   EXPLORATION, not wired into the build — the frozen production token set
   is in ../DESIGN.md.
   ========================================================================= */

:root {

  /* ---------------------------------------------------------------------
     1. SURFACE / BACKGROUND
     canvas -> surface -> surface-raised is a 3-step lift, each step a
     hairline border, never a shadow-only lift.
     --------------------------------------------------------------------- */
  --sop-color-canvas:          #0a0b0f; /* from A/B/C/D: near-black page background behind every card */
  --sop-color-surface:         #14161e; /* from B/C: KPI-tile / agent-card fill, one step lighter than canvas */
  --sop-color-surface-sunken:  #0f1116; /* from D: inset numbered pipeline-step rows sit slightly darker than the modal surface */
  --sop-color-surface-raised:  #181b26; /* from D: the provenance modal itself reads one step lighter than a plain card, sitting on a dimmed page */
  --sop-color-scrim:           rgba(6, 7, 10, 0.72); /* from D: the page behind "How this number was produced" is dimmed, not just covered */
  --sop-color-border:          rgba(255, 255, 255, 0.08); /* from B/C/D: thin, low-opacity hairline card borders throughout */
  --sop-color-border-strong:   rgba(255, 255, 255, 0.16); /* derived: heavier divider, e.g. under a table header row */
  --sop-color-step-connector:  rgba(255, 255, 255, 0.14); /* from D: the connector between the 5 numbered provenance steps */

  /* ---------------------------------------------------------------------
     2. TEXT HIERARCHY
     --------------------------------------------------------------------- */
  --sop-color-text-primary:    #f5f6f8; /* from B/D: headline and KPI-number near-white */
  --sop-color-text-secondary:  #9aa0ab; /* from B: chart-legend / narrative-rail body copy grey */
  --sop-color-text-muted:      #828997; /* from A/C: dim tracked-uppercase micro-labels ("TRANSFER CONFIDENCE", "VERDICT"). Lifted from the screenshot's #6b7280, which measured 3.73:1 on surface — under AA for 11px text. Now 5.14:1 surface / 4.88:1 raised / 5.60:1 canvas. */
  --sop-color-text-inverse:    #14161c; /* derived: text set on a solid-fill light chip (e.g. a filled status pill) */

  /* ---------------------------------------------------------------------
     3. BRAND / ACCENT HUE — the ONE decorative hue in the system (see the
     restrained-hue policy above). Purple recurs as pure identity/nav
     across the deck, never as a data-series color: the ACT chip in A, the
     "Explain" mode dot + UOKG drawer icon in B, the Simulation-Agent card
     in C. Used sparingly here too: selected-tab underline, focus ring,
     one icon — never a chart series.
     --------------------------------------------------------------------- */
  --sop-color-brand:           #a78bfa; /* from A/B/C: purple accent, read directly off the dark screenshots */
  --sop-color-brand-subtle:    rgba(167, 139, 250, 0.16); /* derived: tint for selected-nav/focus backgrounds */

  /* ---------------------------------------------------------------------
     4. IBCS NOTATION INK — actual / plan / forecast / previous year
     None of the 4 screenshots contain real IBCS bar/variance notation (no
     scenario bars anywhere in the deck). This whole block is therefore
     DERIVED from IBCS convention: one neutral ink, distinguished by FILL
     STYLE and WEIGHT alone, never by hue — hue stays reserved entirely
     for the good/bad/warn/info signal in section 5.
     --------------------------------------------------------------------- */
  --sop-color-ink:              #f5f6f8; /* derived: same value as --sop-color-text-primary — actual = solid fill in this ink, plan/budget = outline stroke in this ink */
  --sop-color-ink-soft:         #8b90a0; /* derived: mid-grey — forecast = hatched fill in this ink */
  --sop-color-ink-faint:        #646a78; /* derived: dimmest grey — previous year = flat SOLID fill in this ink ("light solid": present, but visually receded behind actual). Lifted from #565b68, which measured 2.66:1 on surface — under the 3:1 non-text floor for a data mark. Now 3.33:1 surface / 3.17:1 raised. */

  /* ---------------------------------------------------------------------
     5. SEMANTIC PAIR/QUAD — good / bad / warn / info
     Clearest direct evidence in the set: B's KPI deltas (▲12.4%/▲12.0% in
     green, ▼2.1% in red-adjacent), C's verdict chips (green "Primary
     cause"/"Validates Market" vs amber "Correlation only"), D's amber
     "WARNING (-5.8%)" and green "HIGH" confidence badge, and B/D's blue
     hyperlinks + tab indicator. Per the task's accessibility requirement
     this pair is NEVER carried by hue alone in the utility classes below:
     .variance-positive/.variance-negative always render a ▲/▼ glyph via
     ::before (section 15), and .status-dot is always paired with text,
     never shown alone (section 13).
     --------------------------------------------------------------------- */
  --sop-color-good:             #34d399; /* from B: up-delta green, e.g. "▲12.4%" */
  --sop-color-good-bg:          rgba(52, 211, 153, 0.12);
  --sop-color-bad:              #f87171; /* from B/C: down-delta / "Causes" red */
  --sop-color-bad-bg:           rgba(248, 113, 113, 0.12);
  --sop-color-warn:             #fbbf24; /* from C/D: amber "Below target" dot, "WARNING (-5.8%)", HITL/approval-required pill */
  --sop-color-warn-bg:          rgba(251, 191, 36, 0.12);
  --sop-color-info:             #22d3ee; /* from B/D: "Understand" tab dot, "Why?"/provenance hyperlinks. Moved off the screenshot's #60a5fa blue, which measured ΔE 10.2 (normal vision) / 0.3 (deutan) against the brand purple — indistinguishable. Cyan measures ΔE 21.2 normal / 11.4 deutan, and 9.99:1 on surface. */
  --sop-color-info-bg:          rgba(34, 211, 238, 0.12);

  /* ---------------------------------------------------------------------
     6. CHART INK
     --------------------------------------------------------------------- */
  --sop-color-chart-grid:       rgba(255, 255, 255, 0.06); /* derived: faint gridline */
  --sop-color-chart-axis:       rgba(255, 255, 255, 0.16); /* derived: axis line/tick, one step stronger than grid */
  --sop-color-chart-actual:     var(--sop-color-ink);       /* derived: actual = solid ink fill, see .mark-actual */
  --sop-color-chart-plan:       var(--sop-color-ink);       /* derived: plan/budget = same ink, OUTLINE only, see .mark-plan */
  --sop-color-chart-forecast:   var(--sop-color-ink-soft);  /* derived: forecast = lighter ink, HATCHED, see .mark-forecast */
  --sop-color-chart-prior-year: var(--sop-color-ink-faint); /* derived: previous year = faintest ink, flat SOLID fill, see .mark-prior-year */
  --sop-color-chart-highlight:  var(--sop-color-brand);     /* from B: the one purple-outlined "currently focused" KPI tile — marks the single selected metric on a chart, sparingly */

  /* ---------------------------------------------------------------------
     7. CONFIDENCE / FORECAST-CONE SCALE
     Directly observed in A's "TRANSFER CONFIDENCE" legend: line thickness
     encodes a 4-step confidence tier (0.70–1.00 High / 0.40–0.69 Medium /
     0.20–0.39 Low / 0.00–0.19 Very Low), and the legend states the lowest
     tier is additionally dashed ("Dashed = experimental / low
     confidence"). Reused below, by name, for the P10/P50/P90 forecast
     cone: P50 (the median, most-likely line) takes the high-confidence
     treatment; the P10/P90 tail bounds take the low-confidence dashed
     treatment. No new hue is introduced for uncertainty — per the
     restrained-hue policy, confidence is carried entirely by weight and
     dash, in neutral ink.
     --------------------------------------------------------------------- */
  --sop-confidence-weight-high:       3px;   /* from A: 0.70–1.00 tier, thickest line in the legend */
  --sop-confidence-weight-medium:     2px;   /* from A: 0.40–0.69 tier */
  --sop-confidence-weight-low:        1.5px; /* from A: 0.20–0.39 tier */
  --sop-confidence-weight-verylow:    1px;   /* from A: 0.00–0.19 tier, thinnest */
  --sop-confidence-dasharray-verylow: 3 3;   /* from A: "Dashed = experimental / low confidence" — SVG stroke-dasharray */

  --sop-cone-p50-weight:      var(--sop-confidence-weight-high); /* derived: forecast-cone median = high-confidence line */
  --sop-cone-p50-style:       solid;
  --sop-cone-band-weight:     var(--sop-confidence-weight-low);  /* derived: P10/P90 tail bounds = low-confidence line */
  --sop-cone-band-style:      dashed;
  --sop-cone-band-dasharray:  var(--sop-confidence-dasharray-verylow);
  --sop-cone-band-fill:       rgba(245, 246, 248, 0.06); /* derived: faint neutral-ink tint between P10 and P90 — no dedicated "uncertainty" hue, per the restrained-hue policy */

  /* ---------------------------------------------------------------------
     8. BORDER / RADIUS / SHADOW (no glow — see header)
     --------------------------------------------------------------------- */
  --sop-border-width:            1px;   /* from B/C/D: consistent thin hairline card borders throughout */
  --sop-radius-sm:                6px;  /* from A: small icon chips (edition badges, agent-card icons) */
  --sop-radius-md:                10px; /* from B/C: KPI tiles and content cards */
  --sop-radius-lg:                16px; /* from D: the drill-down modal's outer corner */
  --sop-radius-pill:             999px; /* from C/D: verdict badges, "HITL"/"HIGH" status pills */

  --sop-shadow-sm:               0 1px 2px rgba(0, 0, 0, 0.4); /* derived: neutral elevation only (modal separation from a dimmed page); glow deliberately omitted, see header */
  --sop-shadow-focus-ring:       0 0 0 3px var(--sop-color-brand-subtle); /* derived: crisp 0-blur ring, not a bloom — accessible focus indicator */

  /* ---------------------------------------------------------------------
     9. TYPOGRAPHY
     System font stack only — the screenshots render in a geometric
     grotesque consistent with SF/Segoe system rendering; no distinctive
     custom-font characteristics were visible, so no external font is
     assumed or required. No CDN, no JS anywhere in this file.
     --------------------------------------------------------------------- */
  --sop-font-sans: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; /* derived: system stack matching the deck's rendering, per task requirement */

  /* Type scale — sizes read off the deck's clear hierarchy: big bold hero
     number > bold slide headline > card title > body > table cell >
     tracked uppercase micro-label. */
  --sop-text-display:  34px; /* from B/D: KPI hero numbers (₹4.24L, ₹4.24L/day) */
  --sop-text-h1:        28px; /* from A/B/C/D: bold slide headline, consistently ~28-32px */
  --sop-text-h2:        16px; /* from B: card/section titles */
  --sop-text-body:      14px; /* from B/D: right-rail narrative paragraphs and card body copy */
  --sop-text-small:     13px; /* derived: secondary/table-cell text, one step below body */
  --sop-text-label:     11px; /* from A/C: tracked uppercase micro-labels ("TRANSFER CONFIDENCE", "VERDICT") */

  --sop-weight-regular:  400;
  --sop-weight-medium:   500;
  --sop-weight-semibold: 600; /* from A/C: micro-label and card-title weight */
  --sop-weight-bold:     700; /* from B/D: KPI hero numbers and headlines */

  --sop-label-tracking:  0.06em; /* from A/C: visible letter-spacing on uppercase micro-labels */

  /* Tabular numerals — from B/D: KPI numbers and the pipeline's numbered
     step figures sit right-aligned at equal width; direct evidence for
     tabular (fixed-width) digit rendering everywhere. */
  --sop-font-feature-tabular: "tnum" 1, "lnum" 1;

  /* One scale for money, one for units — both share the same base sizes
     so a money tile and a unit tile sit at equal visual weight (B's
     Revenue/Orders/AOV row), differing only in a smaller muted suffix for
     scale words ("L", "K", "/day") — from B/D: "₹4.24L/day", "20.6K/day",
     "5.07x" all pair a bold number with a smaller, muted trailing unit. */
  --sop-num-lg:            34px; /* hero KPI figure, money or unit */
  --sop-num-md:            20px; /* secondary figure */
  --sop-num-sm:            14px; /* table-cell figure */
  --sop-num-suffix-size:   0.55em; /* derived: relative size of a trailing "/day", "L", "K", "x" unit suffix */

  /* ---------------------------------------------------------------------
     10. SPACING RHYTHM
     Card internal padding reads ~20-24px throughout (A/B/C/D); gaps
     between sibling cards/tiles read ~12-16px. An 8px-multiple scale
     covers both cleanly.
     --------------------------------------------------------------------- */
  --sop-space-1:  4px;
  --sop-space-2:  8px;
  --sop-space-3: 12px; /* from A/B/C/D: gap between sibling KPI tiles / agent cards */
  --sop-space-4: 16px;
  --sop-space-5: 20px; /* from A/B/C/D: card internal padding (lower end) */
  --sop-space-6: 24px; /* from A/B/C/D: card internal padding (upper end) / page gutter */
  --sop-space-8: 32px;
  --sop-space-10: 40px;

  /* ---------------------------------------------------------------------
     11. TABLE / GRID
     --------------------------------------------------------------------- */
  --sop-table-row-height:  40px;                            /* derived, comfortable with --sop-text-small + --sop-space-2 padding */
  --sop-table-header-bg:   var(--sop-color-surface-sunken); /* derived */
  --sop-table-stripe-bg:   rgba(255, 255, 255, 0.025);      /* derived: faint zebra striping, well under WCAG-irrelevant decorative threshold */

  /* ---------------------------------------------------------------------
     12. KPI-TILE ANATOMY
     From B/D: micro-label with an info affordance ("Revenue ⓘ") + big
     bold hero number + a colored delta row (direction glyph + comparison
     basis, e.g. "▲12.4% vs Apr 1 – Apr 27") + an inline "Why?" drill-in
     link. Tokens below size the container; the .tile utility (section 16)
     expresses the anatomy itself.
     --------------------------------------------------------------------- */
  --sop-tile-padding:   var(--sop-space-5); /* from B: KPI tile internal padding */
  --sop-tile-radius:    var(--sop-radius-md);
  --sop-tile-gap:       var(--sop-space-2); /* from B: vertical gap between label / number / delta rows */
  --sop-tile-info-size: 14px;               /* from B/D: the small "ⓘ" info-affordance glyph beside each KPI-tile label */

  /* ---------------------------------------------------------------------
     13. STATUS DOTS — KPI health
     From B's left-rail "KPI HEALTH" list: a colored dot always paired
     with a label ("● Revenue", "● Supply Risk"), never a bare dot. Colors
     reuse the good/warn/bad tokens from section 5 — no new hue.
     --------------------------------------------------------------------- */
  --sop-dot-size: 8px; /* from B: KPI Health list dot diameter */

  /* ---------------------------------------------------------------------
     14. NARRATIVE RAIL
     From B/D: the right-hand story panel sits directly on canvas with no
     card border — visually distinct from the hairline-bordered data grid
     by measure and typography alone, not a box. The one bordered element
     inside it is a callout: D's "Core tenet" box and B's boxed aside both
     carry a colored LEFT-border accent, in the info blue (never brand
     purple — purple stays reserved for nav/identity per the hue policy).
     --------------------------------------------------------------------- */
  --sop-color-rail-accent:          var(--sop-color-info); /* from D/B: callout left-border accent */
  --sop-rail-max-width:             320px; /* derived: comfortable reading measure for the right-hand panel in B/D */
  --sop-rail-callout-border-width:  3px;   /* from D: the "Core tenet" box's left-border accent reads heavier than the standard 1px hairline */
}

/* =============================================================================
   LIGHT THEME — explicit opt-in override, NOT the default
   Dark is primary per the design brief. Nothing in this file switches to
   light automatically (deliberately no `@media (prefers-color-scheme:
   light)` query) — that would make light "the default" for any user whose
   OS happens to be set to light, exactly the inversion we're avoiding.
   Apply light explicitly: <html data-theme="light">. None of the 4
   reference screenshots show a light variant, so every value below is
   DERIVED as a straight light-inversion of the dark tokens above, kept
   only for parity with callers that still need a light surface (e.g. a
   printed handout).
   ========================================================================= */
[data-theme="light"] {
  --sop-color-canvas:          #f7f7f8; /* derived: light inversion of --sop-color-canvas */
  --sop-color-surface:         #ffffff; /* derived: light inversion of --sop-color-surface */
  --sop-color-surface-sunken:  #eef0f3; /* derived */
  --sop-color-surface-raised:  #ffffff; /* derived: modal sits flush with surface in the light variant */
  --sop-color-scrim:           rgba(20, 22, 28, 0.4); /* derived */
  --sop-color-border:          #e1e3e8; /* derived */
  --sop-color-border-strong:   #c7cad2; /* derived */
  --sop-color-step-connector:  #d5d8de; /* derived */

  --sop-color-text-primary:    #14161c; /* derived */
  --sop-color-text-secondary:  #4a4f5b; /* derived */
  --sop-color-text-muted:      #666d79; /* derived: was #868c98 = 3.38:1 on white, under AA for 11px labels. Now 5.21:1. */
  --sop-color-text-inverse:    #f5f6f8; /* derived */

  --sop-color-brand:           #6d28d9; /* derived: darkened for 4.5:1+ contrast on white */
  --sop-color-brand-subtle:    #efe9fc; /* derived */

  --sop-color-ink:              #14161c; /* derived */
  --sop-color-ink-soft:         #767c8a; /* derived: was #9096a3 = 2.97:1 on white, under the 3:1 mark floor. Now 4.18:1. */
  --sop-color-ink-faint:        #858b98; /* derived: was #c7cad2 = 1.64:1 on white — invisible as a mark. Now 3.25:1 on white / 3.04:1 on canvas. */

  --sop-color-good:             #1a7a42; /* derived: darkened for AA on white */
  --sop-color-good-bg:          #e7f5eb;
  --sop-color-bad:              #b3261e; /* derived: darkened for AA on white */
  --sop-color-bad-bg:           #fbeae8;
  --sop-color-warn:             #966107; /* derived: darkened for AA on white */
  --sop-color-warn-bg:          #fdf2dc;
  --sop-color-info:             #1d4ed8; /* derived */
  --sop-color-info-bg:          #e9eefc;

  --sop-color-chart-grid:       #e8e9ec; /* derived */
  --sop-color-chart-axis:       #b8bcc6; /* derived */

  --sop-cone-band-fill:         rgba(20, 22, 28, 0.05); /* derived: light-theme equivalent tint */

  --sop-shadow-sm:               0 1px 2px rgba(20, 22, 28, 0.06); /* derived */
  --sop-shadow-focus-ring:       0 0 0 3px var(--sop-color-brand-subtle);
}

/* =============================================================================
   UTILITY CLASSES — the minimum set every mockup needs
   ========================================================================= */

*, *::before, *::after { box-sizing: border-box; }

body {
  background: var(--sop-color-canvas);
  color: var(--sop-color-text-primary);
  font-family: var(--sop-font-sans);
  font-size: var(--sop-text-body);
  line-height: 1.5;
}

/* --- panel: generic card/section container (chart cards, list cards —
   every module in the screenshots is one of these) ---------------------- */
.panel {
  background: var(--sop-color-surface);
  border: var(--sop-border-width) solid var(--sop-color-border);
  border-radius: var(--sop-radius-md);
  padding: var(--sop-space-5);
}
.panel + .panel { margin-top: var(--sop-space-4); }

/* --- modal: the provenance drill-down surface (from D) ------------------ */
.modal-scrim {
  background: var(--sop-color-scrim); /* from D: dimmed page behind the "How this number was produced" modal */
}
.modal {
  background: var(--sop-color-surface-raised);
  border: var(--sop-border-width) solid var(--sop-color-border);
  border-radius: var(--sop-radius-lg);
  box-shadow: var(--sop-shadow-sm);
  padding: var(--sop-space-6);
}
.step-connector {
  border-left: var(--sop-border-width) solid var(--sop-color-step-connector); /* from D: connector between numbered pipeline steps */
}

/* --- section-header: tracked-uppercase kicker + bold title, e.g.
   "ACT 4 · THE COMPOUNDING MOAT" / "TREND SNAPSHOT" ---------------------- */
.section-header { margin-bottom: var(--sop-space-4); }
.section-header .kicker {
  display: block;
  font-size: var(--sop-text-label);
  font-weight: var(--sop-weight-semibold);
  letter-spacing: var(--sop-label-tracking);
  text-transform: uppercase;
  color: var(--sop-color-text-muted);
  margin-bottom: var(--sop-space-1);
}
.section-header .title {
  font-size: var(--sop-text-h2);
  font-weight: var(--sop-weight-semibold);
  color: var(--sop-color-text-primary);
}

/* --- label-muted: standalone micro-label, e.g. a KPI tile's field name -- */
.label-muted {
  font-size: var(--sop-text-label);
  font-weight: var(--sop-weight-semibold);
  letter-spacing: var(--sop-label-tracking);
  text-transform: uppercase;
  color: var(--sop-color-text-muted);
}

/* --- tile: KPI tile anatomy (screenshot B/D) — label row with an info
   affordance, hero number, delta row with a directional glyph + a
   comparison basis, and a "Why?" drill-in link. ------------------------- */
.tile {
  background: var(--sop-color-surface);
  border: var(--sop-border-width) solid var(--sop-color-border);
  border-radius: var(--sop-tile-radius);
  padding: var(--sop-tile-padding);
  display: flex;
  flex-direction: column;
  gap: var(--sop-tile-gap);
}
.tile.is-focused {
  border-color: var(--sop-color-brand); /* from B: the one purple-outlined "focused" Revenue tile */
  box-shadow: var(--sop-shadow-focus-ring); /* crisp 0-blur ring, not the source's blurred glow */
}
/* Note: .tile__label below duplicates .label-muted's declarations rather
   than composing it, since plain CSS has no composition mechanism (no
   build step, per the "no JS" constraint) — apply .label-muted directly
   for the shared muted-label look on a non-tile element. */
.tile__label-row {
  display: flex;
  align-items: center;
  gap: var(--sop-space-1);
}
.tile__label {
  font-size: var(--sop-text-label);
  font-weight: var(--sop-weight-semibold);
  letter-spacing: var(--sop-label-tracking);
  text-transform: uppercase;
  color: var(--sop-color-text-muted);
}
.tile__info {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: var(--sop-tile-info-size);
  height: var(--sop-tile-info-size);
  border-radius: 50%;
  border: 1px solid var(--sop-color-text-muted);
  color: var(--sop-color-text-muted);
  font-size: 10px;
  line-height: 1;
} /* from B/D: the small "ⓘ" info affordance beside every KPI-tile label */
.tile__value {
  font-size: var(--sop-num-lg);
  font-weight: var(--sop-weight-bold);
  color: var(--sop-color-text-primary);
  font-variant-numeric: tabular-nums;
  font-feature-settings: var(--sop-font-feature-tabular);
}
.tile__value .unit {
  font-size: var(--sop-num-suffix-size);
  font-weight: var(--sop-weight-medium);
  color: var(--sop-color-text-secondary);
}
.tile__delta {
  font-size: var(--sop-text-small);
  font-weight: var(--sop-weight-semibold);
  font-variant-numeric: tabular-nums;
}
.tile__delta-basis {
  color: var(--sop-color-text-muted);
  font-weight: var(--sop-weight-regular);
} /* from B: "vs Apr 1 – Apr 27" comparison-basis text trailing the delta */
.tile__why {
  appearance: none;
  background: transparent;
  border: 0;
  padding: 0;
  font-family: inherit;
  display: inline-block;
  margin-top: var(--sop-space-1);
  font-size: var(--sop-text-small);
  font-weight: var(--sop-weight-semibold);
  color: var(--sop-color-info);
  text-decoration: underline;
  cursor: pointer;
} /* appearance/background/border/padding reset added 2026-08-13 (mockup 4): the
     class is meant for a <button> (keyboard-operable, semantic "why" action),
     but had no UA-button reset — first real usage (mockup 4's tile row)
     rendered it as a grey boxed button instead of a text link. */ /* from B/D: "Why?" / provenance drill-in link under the delta row */

/* --- numeric alignment: apply to any <td>/<span> holding a figure ------ */
.num {
  font-variant-numeric: tabular-nums;
  font-feature-settings: var(--sop-font-feature-tabular);
  text-align: right;
  white-space: nowrap;
}
.num--money { font-size: var(--sop-num-md); font-weight: var(--sop-weight-bold); }
.num--unit  { font-size: var(--sop-num-md); font-weight: var(--sop-weight-semibold); }
.num .unit  { font-size: var(--sop-num-suffix-size); color: var(--sop-color-text-secondary); font-weight: var(--sop-weight-regular); }

/* --- variance-positive / variance-negative -----------------------------
   Color is never the only carrier: each class prepends a directional
   glyph via ::before (▲ / ▼) so the sign survives grayscale print and
   red-green color-vision deficiency; both hues are additionally tuned for
   dark-surface contrast (see token comments in section 5).
   ------------------------------------------------------------------- */
.variance-positive,
.variance-negative {
  display: inline-flex;
  align-items: center;
  gap: 0.25em;
  font-weight: var(--sop-weight-semibold);
  font-variant-numeric: tabular-nums;
}
.variance-positive { color: var(--sop-color-good); }
.variance-positive::before { content: "\25B2"; font-size: 0.75em; } /* ▲ from B: up-arrow glyph beside green deltas */
.variance-negative { color: var(--sop-color-bad); }
.variance-negative::before { content: "\25BC"; font-size: 0.75em; } /* ▼ from B: down-arrow glyph beside red deltas */

/* --- status: KPI-health dot, ALWAYS paired with text (section 13) ------ */
.status {
  display: inline-flex;
  align-items: center;
  gap: var(--sop-space-2);
} /* from B: "KPI HEALTH" list — dot + label, never a bare dot */
.status-dot {
  display: inline-block;
  width: var(--sop-dot-size);
  height: var(--sop-dot-size);
  border-radius: 50%;
  flex: none;
}
.status-dot--good { background: var(--sop-color-good); }
.status-dot--warn { background: var(--sop-color-warn); }
.status-dot--bad  { background: var(--sop-color-bad); }

/* --- rail: narrative/story panel (section 14) --------------------------- */
.rail {
  max-width: var(--sop-rail-max-width);
  color: var(--sop-color-text-secondary);
  font-size: var(--sop-text-body);
  line-height: 1.6;
} /* from B/D: sits directly on canvas, no card border — distinct from the data grid by measure + typography, not a box */
.rail a {
  color: var(--sop-color-info);
  text-decoration: underline;
} /* from B/D: inline links inside rail body copy ("Market Agent", "raw data", "pipeline") */
.rail__callout {
  background: var(--sop-color-surface);
  border-left: var(--sop-rail-callout-border-width) solid var(--sop-color-rail-accent);
  border-radius: var(--sop-radius-sm);
  padding: var(--sop-space-4);
  margin-top: var(--sop-space-4);
} /* from D's "Core tenet" box and B's boxed aside — the one bordered element inside an otherwise borderless rail */

/* --- table: reconciliation / plan grids --------------------------------- */
.table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--sop-text-small);
}
.table th,
.table td {
  padding: var(--sop-space-2) var(--sop-space-3);
  height: var(--sop-table-row-height);
  border-bottom: var(--sop-border-width) solid var(--sop-color-border);
  text-align: left;
}
.table th {
  background: var(--sop-table-header-bg);
  font-size: var(--sop-text-label);
  font-weight: var(--sop-weight-semibold);
  letter-spacing: var(--sop-label-tracking);
  text-transform: uppercase;
  color: var(--sop-color-text-muted);
}
.table td.num { font-variant-numeric: tabular-nums; font-feature-settings: var(--sop-font-feature-tabular); text-align: right; }
.table tbody tr:nth-child(even) td { background: var(--sop-table-stripe-bg); }
.table tfoot td {
  border-top: var(--sop-border-width) solid var(--sop-color-border-strong);
  border-bottom: none;
  font-weight: var(--sop-weight-bold);
}

/* =============================================================================
   IBCS MARK UTILITIES — actual (solid) / plan (outline) / forecast
   (hatched) / previous year (light solid)
   Required by IBCS notation discipline (task brief), not present in the
   source screenshots (none contain scenario-typed bars). Applied to any
   bar/legend-swatch element, e.g. <span class="mark mark-actual"></span>
   next to a chart legend entry, or on a chart's own <rect>/<div> bar.
   ========================================================================= */
.mark {
  display: inline-block;
  width: 1em;
  height: 1em;
  border-radius: 2px;
  vertical-align: -0.15em;
}
.mark-actual {
  /* actual = solid ink fill */
  background: var(--sop-color-chart-actual);
}
.mark-plan {
  /* plan/budget = outline only, no fill, so it never competes visually with actual */
  background: transparent;
  border: 2px solid var(--sop-color-chart-plan);
}
.mark-forecast {
  /* forecast = hatched + lighter ink, pure CSS diagonal hatch (no image/SVG needed) */
  background: repeating-linear-gradient(
    45deg,
    var(--sop-color-chart-forecast) 0,
    var(--sop-color-chart-forecast) 1.5px,
    transparent 1.5px,
    transparent 5px
  );
  border: 1px solid var(--sop-color-chart-forecast);
}
.mark-prior-year {
  /* previous year = light solid fill — faintest ink, no hatch, no outline-only treatment, so it reads as "present but receded" next to actual */
  background: var(--sop-color-chart-prior-year);
}

/* =============================================================================
   CONFIDENCE LINE UTILITIES — from A's TRANSFER CONFIDENCE legend
   Apply to a legend swatch (<span class="conf-line conf-line--high">) or,
   for chart strokes, read the --sop-confidence-weight-* / --sop-cone-*
   custom properties directly onto an SVG <path>/<line> stroke-width and
   stroke-dasharray (plain CSS var() works on SVG presentation attributes
   too).
   ========================================================================= */
.conf-line {
  display: inline-block;
  width: 2em;
  border-top-style: solid;
  border-top-color: var(--sop-color-ink-soft);
  vertical-align: middle;
}
.conf-line--high    { border-top-width: var(--sop-confidence-weight-high); }
.conf-line--medium  { border-top-width: var(--sop-confidence-weight-medium); }
.conf-line--low     { border-top-width: var(--sop-confidence-weight-low); }
.conf-line--verylow {
  border-top-width: var(--sop-confidence-weight-verylow);
  border-top-style: dashed;
} /* from A: thickness = confidence tier, dashed = experimental/very-low */

/* --- forecast-cone marks: P50 median + P10/P90 band, reusing the
   confidence scale above (see section 7 token comments) ------------------ */
.cone-p50 {
  stroke-width: var(--sop-cone-p50-weight);
  stroke-dasharray: none;
}
.cone-band {
  stroke-width: var(--sop-cone-band-weight);
  stroke-dasharray: var(--sop-cone-band-dasharray);
  fill: var(--sop-cone-band-fill);
}

/* ===================== MERGED MOCKUP STYLES ===================== */

/* ===== 01-layout-shell ===== */

/* =============================================================================
   01-layout-shell.html — MOCKUP 1 of 5 (SCOPE.md §9)
   Scope of this mockup: the SHELL — page skeleton, headline band, small-multiples
   grid, narrative rail, table collapse. Chart encoding is deliberately minimal;
   mockup 2 (scenario comparison) is where the charts get their real treatment.
   Every number comes from mockups/data.js, generated by the engine.
   ========================================================================== */

*, *::before, *::after { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
body {
  background: var(--sop-color-canvas);
  color: var(--sop-color-text-primary);
  font-family: var(--sop-font-sans);
  font-size: var(--sop-text-body);
  line-height: 1.5;
  -webkit-font-smoothing: antialiased;
}

/* --- page frame ----------------------------------------------------------- */
.page { max-width: 1560px; margin: 0 auto; padding: 0 var(--sop-space-6) var(--sop-space-8); }

.topbar {
  display: flex; align-items: center; gap: var(--sop-space-5);
  padding: var(--sop-space-4) 0;
  border-bottom: 1px solid var(--sop-color-border);
}
.topbar__title { font-size: var(--sop-text-h2); font-weight: 600; margin: 0; letter-spacing: -0.01em; }
.topbar__sub { color: var(--sop-color-text-muted); font-size: var(--sop-text-label);
  text-transform: uppercase; letter-spacing: 0.08em; margin-top: 2px; }
.topbar__spacer { flex: 1; }

/* mode switcher — three lenses on one canvas, no navigation (SCOPE §6b) */
.modes { display: flex; gap: 2px; background: var(--sop-color-surface-sunken);
  border: 1px solid var(--sop-color-border); border-radius: var(--sop-radius-md); padding: 2px; }
.modes__btn {
  appearance: none; border: 0; background: transparent; cursor: pointer;
  color: var(--sop-color-text-secondary); font: inherit; font-size: var(--sop-text-small);
  padding: 6px 14px; border-radius: calc(var(--sop-radius-md) - 2px);
}
.modes__btn[aria-selected="true"] { background: var(--sop-color-brand-subtle); color: var(--sop-color-text-primary); }
.modes__btn:focus-visible { outline: 2px solid var(--sop-color-brand); outline-offset: 1px; }

.iconbtn {
  appearance: none; cursor: pointer; font: inherit; font-size: var(--sop-text-small);
  color: var(--sop-color-text-secondary); background: var(--sop-color-surface);
  border: 1px solid var(--sop-color-border); border-radius: var(--sop-radius-md); padding: 6px 12px;
}
.iconbtn:hover { color: var(--sop-color-text-primary); border-color: var(--sop-color-border-strong); }

/* --- headline band — the 5-second read ------------------------------------ */
.headline {
  display: grid; grid-template-columns: minmax(0, 1.35fr) minmax(0, 1fr);
  gap: var(--sop-space-5); align-items: stretch;
  padding: var(--sop-space-5) 0 var(--sop-space-4);
}
.verdict { min-width: 0; }
.verdict__label { color: var(--sop-color-text-muted); font-size: var(--sop-text-label);
  text-transform: uppercase; letter-spacing: 0.08em; }
.verdict__line { font-size: var(--sop-text-h1); font-weight: 600; letter-spacing: -0.02em;
  margin: var(--sop-space-2) 0 var(--sop-space-2); line-height: 1.2; }
.verdict__because { color: var(--sop-color-text-secondary); max-width: 62ch; margin: 0; }

.constraint {
  border: 1px solid var(--sop-color-border); border-left: 3px solid var(--sop-color-warn);
  background: var(--sop-color-surface); border-radius: var(--sop-radius-md);
  padding: var(--sop-space-4); display: flex; flex-direction: column; justify-content: center;
}
.constraint__label { color: var(--sop-color-text-muted); font-size: var(--sop-text-label);
  text-transform: uppercase; letter-spacing: 0.08em; }
.constraint__what { font-size: var(--sop-text-h2); font-weight: 600; margin: var(--sop-space-2) 0 4px; }
.constraint__detail { color: var(--sop-color-text-secondary); font-size: var(--sop-text-small); margin: 0; }

/* --- stat tiles ----------------------------------------------------------- */
.tiles { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: var(--sop-space-4);
  padding-bottom: var(--sop-space-5); }
.tile { background: var(--sop-color-surface); border: 1px solid var(--sop-color-border);
  border-radius: var(--sop-radius-md); padding: var(--sop-space-4); min-width: 0; }
.tile__label { color: var(--sop-color-text-muted); font-size: var(--sop-text-label);
  text-transform: uppercase; letter-spacing: 0.08em; display: flex; align-items: center; gap: 6px; }
.tile__value { font-size: var(--sop-text-display); font-weight: 600; letter-spacing: -0.02em;
  margin-top: var(--sop-space-2); font-variant-numeric: tabular-nums; line-height: 1.1; }
.tile__foot { margin-top: 6px; font-size: var(--sop-text-small); color: var(--sop-color-text-secondary);
  display: flex; align-items: baseline; gap: 8px; flex-wrap: wrap; }
.delta { font-variant-numeric: tabular-nums; font-weight: 600; }
.delta--good { color: var(--sop-color-good); }
.delta--bad  { color: var(--sop-color-bad); }
.delta--flat { color: var(--sop-color-text-muted); }
.basis { color: var(--sop-color-text-muted); }

/* "why?" affordance — the provenance modal is mockup 3, this is the hook for it */
.why {
  appearance: none; background: transparent; border: 0; padding: 0; cursor: help;
  color: var(--sop-color-info); font: inherit; font-size: var(--sop-text-label);
  text-decoration: underline; text-underline-offset: 2px;
}

/* --- main + rail ---------------------------------------------------------- */
.main { display: grid; grid-template-columns: minmax(0, 1fr) 340px; gap: var(--sop-space-5); align-items: start; }

.panel { background: var(--sop-color-surface); border: 1px solid var(--sop-color-border);
  border-radius: var(--sop-radius-lg); padding: var(--sop-space-5); }
.panel__head { display: flex; align-items: baseline; gap: var(--sop-space-3); margin-bottom: var(--sop-space-2); }
.panel__title { font-size: var(--sop-text-h2); font-weight: 600; margin: 0; }
.panel__note { color: var(--sop-color-text-muted); font-size: var(--sop-text-small); margin: 0; }

/* small-multiples grid: rows = metrics, columns = scenarios, shared y per row */
.sm { display: grid; grid-template-columns: 168px repeat(3, minmax(0, 1fr)); gap: 0; }
.sm__colhead {
  padding: var(--sop-space-3) var(--sop-space-3) var(--sop-space-2);
  border-bottom: 1px solid var(--sop-color-border-strong);
  display: flex; align-items: center; gap: 8px;
}
.sm__colhead-name { font-size: var(--sop-text-small); font-weight: 600; }
.sm__colhead-sub { color: var(--sop-color-text-muted); font-size: var(--sop-text-label);
  font-variant-numeric: tabular-nums; margin-left: auto; }
.sm__corner { border-bottom: 1px solid var(--sop-color-border-strong); }

.sm__rowhead {
  padding: var(--sop-space-4) var(--sop-space-3) var(--sop-space-4) 0;
  border-bottom: 1px solid var(--sop-color-border);
  display: flex; flex-direction: column; justify-content: center;
}
.sm__rowhead-name { font-size: var(--sop-text-small); font-weight: 600; }
.sm__rowhead-unit { color: var(--sop-color-text-muted); font-size: var(--sop-text-label);
  text-transform: uppercase; letter-spacing: 0.06em; margin-top: 2px; }
.sm__rowhead-scale { color: var(--sop-color-text-muted); font-size: var(--sop-text-label);
  margin-top: 6px; font-variant-numeric: tabular-nums; }

.sm__cell { padding: var(--sop-space-3); border-bottom: 1px solid var(--sop-color-border);
  border-left: 1px solid var(--sop-color-border); min-width: 0; }
.sm__cell svg { display: block; width: 100%; height: auto; }

/* chart primitives */
.grid-line { stroke: var(--sop-color-chart-grid); stroke-width: 1; }
.axis-line { stroke: var(--sop-color-chart-axis); stroke-width: 1; }
.ref-line  { stroke: var(--sop-color-text-muted); stroke-width: 1; stroke-dasharray: 3 3; }
.tick-text { fill: var(--sop-color-text-muted); font-size: 9px; font-family: var(--sop-font-sans); }
.mark-hit  { fill: transparent; cursor: pointer; }

/* legend — identity is never colour alone (SCOPE §6b: pattern, not hue) */
.legend { display: flex; flex-wrap: wrap; gap: var(--sop-space-4); align-items: center;
  margin-top: var(--sop-space-4); padding-top: var(--sop-space-3);
  border-top: 1px solid var(--sop-color-border); font-size: var(--sop-text-small);
  color: var(--sop-color-text-secondary); }
.legend__item { display: flex; align-items: center; gap: 7px; }
.legend__swatch { width: 20px; height: 11px; display: inline-block; }

/* --- narrative rail ------------------------------------------------------- */
.rail { display: flex; flex-direction: column; gap: var(--sop-space-4); position: sticky; top: var(--sop-space-4); }
.rail__section { background: var(--sop-color-surface); border: 1px solid var(--sop-color-border);
  border-radius: var(--sop-radius-lg); padding: var(--sop-space-4); }
.rail__label { color: var(--sop-color-text-muted); font-size: var(--sop-text-label);
  text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: var(--sop-space-3); }
.rail__list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: var(--sop-space-3); }
.rail__item { display: flex; gap: 9px; font-size: var(--sop-text-small); line-height: 1.45;
  color: var(--sop-color-text-secondary); }
.rail__item strong { color: var(--sop-color-text-primary); font-weight: 600; }
.dot { width: 8px; height: 8px; border-radius: 50%; flex: none; margin-top: 6px; }
.dot--good { background: var(--sop-color-good); }
.dot--warn { background: var(--sop-color-warn); }
.dot--bad  { background: var(--sop-color-bad); }
.dot--info { background: var(--sop-color-info); }
.rail__callout { border-left: 3px solid var(--sop-color-info); background: var(--sop-color-surface-sunken);
  border-radius: var(--sop-radius-sm); padding: var(--sop-space-3); font-size: var(--sop-text-small);
  color: var(--sop-color-text-secondary); }

/* --- table collapse (design rule 13) -------------------------------------- */
.tablewrap { margin-top: var(--sop-space-5); }
.tablewrap[hidden] { display: none; }
table { width: 100%; border-collapse: collapse; font-size: var(--sop-text-small);
  font-variant-numeric: tabular-nums; }
th, td { text-align: right; padding: 0 var(--sop-space-3); height: var(--sop-table-row-height);
  border-bottom: 1px solid var(--sop-color-border); }
th:first-child, td:first-child { text-align: left; }
thead th { background: var(--sop-table-header-bg); color: var(--sop-color-text-muted);
  font-size: var(--sop-text-label); text-transform: uppercase; letter-spacing: 0.06em;
  font-weight: 600; border-bottom: 1px solid var(--sop-color-border-strong); }
tbody tr:nth-child(even) { background: var(--sop-table-stripe-bg); }

/* --- tooltip -------------------------------------------------------------- */
.tip { position: fixed; pointer-events: none; z-index: 50; opacity: 0; transition: opacity 90ms linear;
  background: var(--sop-color-surface-raised); border: 1px solid var(--sop-color-border-strong);
  border-radius: var(--sop-radius-md); padding: 10px 12px; font-size: var(--sop-text-small);
  min-width: 168px; max-width: 260px; }
.tip[data-show="1"] { opacity: 1; }
.tip__head { font-weight: 600; margin-bottom: 6px; }
.tip__row { display: flex; justify-content: space-between; gap: var(--sop-space-4);
  color: var(--sop-color-text-secondary); font-variant-numeric: tabular-nums; }
.tip__row b { color: var(--sop-color-text-primary); font-weight: 600; }
.tip__foot { margin-top: 7px; padding-top: 6px; border-top: 1px solid var(--sop-color-border);
  color: var(--sop-color-text-muted); font-size: var(--sop-text-label); }

/* --- footer --------------------------------------------------------------- */
.foot { margin-top: var(--sop-space-6); padding-top: var(--sop-space-4);
  border-top: 1px solid var(--sop-color-border); color: var(--sop-color-text-muted);
  font-size: var(--sop-text-small); display: flex; gap: var(--sop-space-5); flex-wrap: wrap; }

@media (max-width: 1180px) {
  .main { grid-template-columns: minmax(0, 1fr); }
  .rail { position: static; }
  .headline { grid-template-columns: minmax(0, 1fr); }
  .tiles { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}

/* ===== 02-scenario-comparison ===== */

/* =============================================================================
   02-scenario-comparison.html — MOCKUP 2 of 5 (SCOPE.md §9)

   What this mockup is for: comparing scenarios STRUCTURALLY. Mockup 1 answered
   "what happens over the 12 months"; this one answers "which plan, and what does
   choosing it cost me".

   Grammar is prescribed by SCOPE §8b, not chosen here:
     - structural comparison  -> HORIZONTAL bars (vertical columns are reserved
       for time series, so nothing here is a column chart)
     - KPI vs reference       -> BULLET graph
     - bottleneck load        -> GRADED BANDS (safe/strained/critical), never a
       binary over-100% flag
     - every comparison shows VARIANCE vs BASE, not just levels
     - colour encodes variance only; scenario identity is fill pattern
   ========================================================================== */

*, *::before, *::after { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
body {
  background: var(--sop-color-canvas);
  color: var(--sop-color-text-primary);
  font-family: var(--sop-font-sans);
  font-size: var(--sop-text-body);
  line-height: 1.5;
  -webkit-font-smoothing: antialiased;
}
.page { max-width: 1560px; margin: 0 auto; padding: 0 var(--sop-space-6) var(--sop-space-8); }

/* --- chrome --------------------------------------------------------------- */
.topbar { display: flex; align-items: center; gap: var(--sop-space-5);
  padding: var(--sop-space-4) 0; border-bottom: 1px solid var(--sop-color-border); }
.topbar__title { font-size: var(--sop-text-h2); font-weight: 600; margin: 0; letter-spacing: -0.01em; }
.topbar__sub { color: var(--sop-color-text-muted); font-size: var(--sop-text-label);
  text-transform: uppercase; letter-spacing: 0.08em; margin-top: 2px; }
.topbar__spacer { flex: 1; }
.iconbtn { appearance: none; cursor: pointer; font: inherit; font-size: var(--sop-text-small);
  color: var(--sop-color-text-secondary); background: var(--sop-color-surface);
  border: 1px solid var(--sop-color-border); border-radius: var(--sop-radius-md); padding: 6px 12px; }
.iconbtn:hover { color: var(--sop-color-text-primary); border-color: var(--sop-color-border-strong); }

/* --- preset row (SCOPE §3: four anchor presets ship as buttons) ----------- */
.presets { display: flex; gap: var(--sop-space-3); align-items: stretch;
  padding: var(--sop-space-5) 0 var(--sop-space-4); flex-wrap: wrap; }
.preset {
  appearance: none; text-align: left; cursor: pointer; font: inherit;
  background: var(--sop-color-surface); color: var(--sop-color-text-primary);
  border: 1px solid var(--sop-color-border); border-radius: var(--sop-radius-md);
  padding: var(--sop-space-3) var(--sop-space-4); min-width: 208px; flex: 1 1 208px;
}
.preset[aria-pressed="true"] { border-color: var(--sop-color-brand); background: var(--sop-color-brand-subtle); }
.preset[disabled] { cursor: not-allowed; opacity: 0.55; }
.preset__id { color: var(--sop-color-text-muted); font-size: var(--sop-text-label);
  text-transform: uppercase; letter-spacing: 0.08em; display: flex; gap: 6px; align-items: center; }
.preset__name { font-weight: 600; margin: 3px 0 2px; }
.preset__q { color: var(--sop-color-text-secondary); font-size: var(--sop-text-small); margin: 0; }
.tag { font-size: var(--sop-text-label); border: 1px solid var(--sop-color-border-strong);
  border-radius: var(--sop-radius-pill); padding: 0 7px; color: var(--sop-color-text-muted); }

/* --- panels --------------------------------------------------------------- */
.main { display: grid; grid-template-columns: minmax(0, 1fr) 340px; gap: var(--sop-space-5); align-items: start; }
.stack { display: flex; flex-direction: column; gap: var(--sop-space-5); min-width: 0; }
.panel { background: var(--sop-color-surface); border: 1px solid var(--sop-color-border);
  border-radius: var(--sop-radius-lg); padding: var(--sop-space-5); min-width: 0; }
.panel__head { display: flex; align-items: baseline; gap: var(--sop-space-3);
  margin-bottom: var(--sop-space-4); flex-wrap: wrap; }
.panel__title { font-size: var(--sop-text-h2); font-weight: 600; margin: 0; }
.panel__note { color: var(--sop-color-text-muted); font-size: var(--sop-text-small); margin: 0; }

/* --- structural comparison: label | bars | variance ----------------------- */
.cmp { display: grid; grid-template-columns: 168px minmax(0, 1fr) 210px; gap: 0 var(--sop-space-4); }
.cmp__colhead { color: var(--sop-color-text-muted); font-size: var(--sop-text-label);
  text-transform: uppercase; letter-spacing: 0.08em; padding-bottom: var(--sop-space-2);
  border-bottom: 1px solid var(--sop-color-border-strong); }
.cmp__metric { padding: var(--sop-space-4) 0; border-bottom: 1px solid var(--sop-color-border);
  display: flex; flex-direction: column; justify-content: center; }
.cmp__metric-name { font-size: var(--sop-text-small); font-weight: 600; display: flex; align-items: center; gap: 6px; }
.cmp__metric-unit { color: var(--sop-color-text-muted); font-size: var(--sop-text-label);
  text-transform: uppercase; letter-spacing: 0.06em; margin-top: 2px; }
.cmp__bars, .cmp__var { padding: var(--sop-space-4) 0; border-bottom: 1px solid var(--sop-color-border); min-width: 0; }
.cmp__bars svg, .cmp__var svg { display: block; width: 100%; height: auto; }

.bar-label { fill: var(--sop-color-text-secondary); font-size: 10px; font-family: var(--sop-font-sans); }
.bar-value { fill: var(--sop-color-text-primary); font-size: 10px; font-weight: 600;
  font-family: var(--sop-font-sans); }
.tick-text { fill: var(--sop-color-text-muted); font-size: 9px; font-family: var(--sop-font-sans); }
.axis-line { stroke: var(--sop-color-chart-axis); stroke-width: 1; }
.ref-line { stroke: var(--sop-color-text-muted); stroke-width: 1; stroke-dasharray: 3 3; }
.mark-hit { fill: transparent; cursor: pointer; }

/* --- bullet graphs -------------------------------------------------------- */
.bullets { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--sop-space-5); }
.bullet { min-width: 0; }
.bullet__head { display: flex; align-items: baseline; justify-content: space-between; gap: var(--sop-space-3); }
.bullet__name { font-size: var(--sop-text-small); font-weight: 600; }
.bullet__sub { color: var(--sop-color-text-muted); font-size: var(--sop-text-label); }
.bullet svg { display: block; width: 100%; height: auto; margin-top: 6px; }

.bandkey { display: flex; gap: var(--sop-space-4); flex-wrap: wrap; margin-top: var(--sop-space-4);
  padding-top: var(--sop-space-3); border-top: 1px solid var(--sop-color-border);
  font-size: var(--sop-text-small); color: var(--sop-color-text-secondary); }
.bandkey__item { display: flex; align-items: center; gap: 7px; }
.bandkey__swatch { width: 20px; height: 11px; display: inline-block; border-radius: 2px; }

/* --- legend --------------------------------------------------------------- */
.legend { display: flex; flex-wrap: wrap; gap: var(--sop-space-4); align-items: center;
  margin-top: var(--sop-space-4); padding-top: var(--sop-space-3);
  border-top: 1px solid var(--sop-color-border); font-size: var(--sop-text-small);
  color: var(--sop-color-text-secondary); }
.legend__item { display: flex; align-items: center; gap: 7px; }
.legend__swatch { width: 20px; height: 11px; display: inline-block; }

.delta { font-variant-numeric: tabular-nums; font-weight: 600; }
.delta--good { color: var(--sop-color-good); }
.delta--bad { color: var(--sop-color-bad); }
.delta--flat { color: var(--sop-color-text-muted); }

.why { appearance: none; background: transparent; border: 0; padding: 0; cursor: help;
  color: var(--sop-color-info); font: inherit; font-size: var(--sop-text-label);
  text-decoration: underline; text-underline-offset: 2px; }

/* --- rail ----------------------------------------------------------------- */
.rail { display: flex; flex-direction: column; gap: var(--sop-space-4); position: sticky; top: var(--sop-space-4); }
.rail__section { background: var(--sop-color-surface); border: 1px solid var(--sop-color-border);
  border-radius: var(--sop-radius-lg); padding: var(--sop-space-4); }
.rail__label { color: var(--sop-color-text-muted); font-size: var(--sop-text-label);
  text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: var(--sop-space-3); }
.rail__list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: var(--sop-space-3); }
.rail__item { display: flex; gap: 9px; font-size: var(--sop-text-small); line-height: 1.45;
  color: var(--sop-color-text-secondary); }
.rail__item strong { color: var(--sop-color-text-primary); font-weight: 600; }
.dot { width: 8px; height: 8px; border-radius: 50%; flex: none; margin-top: 6px; }
.dot--good { background: var(--sop-color-good); }
.dot--warn { background: var(--sop-color-warn); }
.dot--bad { background: var(--sop-color-bad); }
.dot--info { background: var(--sop-color-info); }
.rail__callout { border-left: 3px solid var(--sop-color-info); background: var(--sop-color-surface-sunken);
  border-radius: var(--sop-radius-sm); padding: var(--sop-space-3); font-size: var(--sop-text-small);
  color: var(--sop-color-text-secondary); }

/* --- table (design rule 13) ---------------------------------------------- */
.tablewrap[hidden] { display: none; }
table { width: 100%; border-collapse: collapse; font-size: var(--sop-text-small); font-variant-numeric: tabular-nums; }
th, td { text-align: right; padding: 0 var(--sop-space-3); height: var(--sop-table-row-height);
  border-bottom: 1px solid var(--sop-color-border); }
th:first-child, td:first-child { text-align: left; }
thead th { background: var(--sop-table-header-bg); color: var(--sop-color-text-muted);
  font-size: var(--sop-text-label); text-transform: uppercase; letter-spacing: 0.06em;
  font-weight: 600; border-bottom: 1px solid var(--sop-color-border-strong); }
tbody tr:nth-child(even) { background: var(--sop-table-stripe-bg); }

/* --- tooltip -------------------------------------------------------------- */
.tip { position: fixed; pointer-events: none; z-index: 50; opacity: 0; transition: opacity 90ms linear;
  background: var(--sop-color-surface-raised); border: 1px solid var(--sop-color-border-strong);
  border-radius: var(--sop-radius-md); padding: 10px 12px; font-size: var(--sop-text-small);
  min-width: 180px; max-width: 280px; }
.tip[data-show="1"] { opacity: 1; }
.tip__head { font-weight: 600; margin-bottom: 6px; }
.tip__row { display: flex; justify-content: space-between; gap: var(--sop-space-4);
  color: var(--sop-color-text-secondary); font-variant-numeric: tabular-nums; }
.tip__row b { color: var(--sop-color-text-primary); font-weight: 600; }
.tip__foot { margin-top: 7px; padding-top: 6px; border-top: 1px solid var(--sop-color-border);
  color: var(--sop-color-text-muted); font-size: var(--sop-text-label); }

.foot { margin-top: var(--sop-space-6); padding-top: var(--sop-space-4);
  border-top: 1px solid var(--sop-color-border); color: var(--sop-color-text-muted);
  font-size: var(--sop-text-small); display: flex; gap: var(--sop-space-5); flex-wrap: wrap; }

@media (max-width: 1180px) {
  .main { grid-template-columns: minmax(0, 1fr); }
  .rail { position: static; }
  .bullets { grid-template-columns: minmax(0, 1fr); }
  .cmp { grid-template-columns: 132px minmax(0, 1fr); }
  .cmp__var, .cmp__colhead--var { display: none; }
}

/* ===== 03-levers-drilldown ===== */

/* =============================================================================
   03-levers-drilldown.html — MOCKUP 3 of 5 (SCOPE.md §9)

   What this mockup is for: the lever sandbox (SCOPE §4) and "click any number,
   see how it was made" — the 5-step provenance modal, SCOPE §6b's centrepiece.

   Two things this mockup deliberately does NOT do, and says so on screen:
   - Levers do not recompute anything live. SCOPE §2 row 7 requires client-side
     recompute for the real build, but that is an IMPLEMENTATION requirement —
     this is still a mockup (SCOPE §9's "Implementation | not started. Do not
     start it.") and there is no JS port of the engine yet (open question in
     HANDOFF-sop-revamp.md). A lever that visually drags but changes nothing
     downstream would be a lie, so every lever renders disabled with a note,
     the same "not wired yet" honesty as mockup 2's disabled S3 Invest preset.
   - The modal shows 5 numbered steps (Demand, Capacity, Rationing, Supply,
     Financials) per tokens.css's own `.step-connector` comment ("connector
     between the 5 numbered provenance steps"). KPI is a closing tie-back
     line under step 5, not a 6th numbered step — SCOPE's "Demand → Capacity →
     Rationing → Supply → Financials → KPI" reads as 5 derivation steps
     landing on one headline number.
   ========================================================================== */

*, *::before, *::after { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
body {
  background: var(--sop-color-canvas);
  color: var(--sop-color-text-primary);
  font-family: var(--sop-font-sans);
  font-size: var(--sop-text-body);
  line-height: 1.5;
  -webkit-font-smoothing: antialiased;
}
.page { max-width: 1560px; margin: 0 auto; padding: 0 var(--sop-space-6) var(--sop-space-8); }

/* --- chrome (matches mockups 1+2) ------------------------------------------ */
.topbar { display: flex; align-items: center; gap: var(--sop-space-5);
  padding: var(--sop-space-4) 0; border-bottom: 1px solid var(--sop-color-border); }
.topbar__title { font-size: var(--sop-text-h2); font-weight: 600; margin: 0; letter-spacing: -0.01em; }
.topbar__sub { color: var(--sop-color-text-muted); font-size: var(--sop-text-label);
  text-transform: uppercase; letter-spacing: 0.08em; margin-top: 2px; }
.topbar__spacer { flex: 1; }
.iconbtn { appearance: none; cursor: pointer; font: inherit; font-size: var(--sop-text-small);
  color: var(--sop-color-text-secondary); background: var(--sop-color-surface);
  border: 1px solid var(--sop-color-border); border-radius: var(--sop-radius-md); padding: 6px 12px; }
.iconbtn:hover { color: var(--sop-color-text-primary); border-color: var(--sop-color-border-strong); }

/* --- scenario tabs ---------------------------------------------------------- */
.scenariotabs { display: flex; gap: var(--sop-space-2); padding: var(--sop-space-5) 0 var(--sop-space-4); }
.scenariotab { appearance: none; cursor: pointer; font: inherit; font-size: var(--sop-text-small); font-weight: 600;
  background: var(--sop-color-surface); color: var(--sop-color-text-secondary);
  border: 1px solid var(--sop-color-border); border-radius: var(--sop-radius-pill); padding: 7px 16px; }
.scenariotab[aria-pressed="true"] { border-color: var(--sop-color-brand); background: var(--sop-color-brand-subtle);
  color: var(--sop-color-text-primary); }

/* --- panels (matches mockups 1+2) ------------------------------------------ */
.main { display: grid; grid-template-columns: minmax(0, 1fr) 340px; gap: var(--sop-space-5); align-items: start; }
.stack { display: flex; flex-direction: column; gap: var(--sop-space-5); min-width: 0; }
.panel { background: var(--sop-color-surface); border: 1px solid var(--sop-color-border);
  border-radius: var(--sop-radius-lg); padding: var(--sop-space-5); min-width: 0; }
.panel__head { display: flex; align-items: baseline; gap: var(--sop-space-3);
  margin-bottom: var(--sop-space-4); flex-wrap: wrap; }
.panel__title { font-size: var(--sop-text-h2); font-weight: 600; margin: 0; }
.panel__note { color: var(--sop-color-text-muted); font-size: var(--sop-text-small); margin: 0; }

/* --- levers panel ------------------------------------------------------------ */
.leverpanel__banner { display: flex; align-items: center; gap: 8px; background: var(--sop-color-warn-bg);
  border: 1px solid var(--sop-color-border); border-radius: var(--sop-radius-sm);
  padding: var(--sop-space-3) var(--sop-space-4); font-size: var(--sop-text-small);
  color: var(--sop-color-text-secondary); margin-bottom: var(--sop-space-4); }
.leverpanel__banner b { color: var(--sop-color-text-primary); }
.levergroups { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--sop-space-5); }
.levergroup__title { font-size: var(--sop-text-label); text-transform: uppercase; letter-spacing: 0.08em;
  color: var(--sop-color-text-muted); margin: 0 0 var(--sop-space-3); padding-bottom: var(--sop-space-2);
  border-bottom: 1px solid var(--sop-color-border-strong); }
.lever { margin-bottom: var(--sop-space-4); }
.lever:last-child { margin-bottom: 0; }
.lever__row { display: flex; justify-content: space-between; align-items: baseline; gap: var(--sop-space-3); }
.lever__label { font-size: var(--sop-text-small); font-weight: 600; }
.lever__val { font-size: var(--sop-text-small); font-variant-numeric: tabular-nums; color: var(--sop-color-text-secondary); }
.lever__range { width: 100%; margin-top: 6px; accent-color: var(--sop-color-text-muted); cursor: not-allowed; opacity: 0.7; }
.lever__range:disabled { cursor: not-allowed; }
.advanced { margin-top: var(--sop-space-5); border-top: 1px solid var(--sop-color-border); padding-top: var(--sop-space-4); }
.advanced > summary { cursor: pointer; font-size: var(--sop-text-small); font-weight: 600;
  color: var(--sop-color-text-secondary); list-style: none; display: flex; align-items: center; gap: 6px; }
.advanced > summary::-webkit-details-marker { display: none; }
.advanced > summary::before { content: "▸"; display: inline-block; transition: transform 100ms linear; }
.advanced[open] > summary::before { transform: rotate(90deg); }
.advanced__body { padding-top: var(--sop-space-4); }

/* --- drill-down grid --------------------------------------------------------- */
.dgrid { width: 100%; border-collapse: collapse; font-size: var(--sop-text-small); font-variant-numeric: tabular-nums; }
.dgrid th, .dgrid td { text-align: center; padding: 0; height: 34px; border-bottom: 1px solid var(--sop-color-border); }
.dgrid th:first-child, .dgrid td:first-child { text-align: left; padding-left: var(--sop-space-2); }
.dgrid thead th { background: var(--sop-table-header-bg); color: var(--sop-color-text-muted);
  font-size: var(--sop-text-label); text-transform: uppercase; letter-spacing: 0.06em;
  font-weight: 600; border-bottom: 1px solid var(--sop-color-border-strong); }
.dgrid tbody tr:nth-child(even) { background: var(--sop-table-stripe-bg); }
.dgrid td .famname { font-weight: 600; }
.dgrid td .famsub { color: var(--sop-color-text-muted); font-size: var(--sop-text-label); display: block; }
.cell { appearance: none; background: transparent; border: 0; cursor: pointer; font: inherit;
  font-variant-numeric: tabular-nums; color: var(--sop-color-text-primary); width: 100%; height: 34px; }
.cell:hover, .cell:focus-visible { background: var(--sop-color-surface-sunken); outline: 1px solid var(--sop-color-border-strong); outline-offset: -1px; }
.cell--unmet { background: var(--sop-color-bad-bg); }
.cell--unmet:hover { background: var(--sop-color-bad-bg); filter: brightness(1.3); }

/* --- legend ------------------------------------------------------------------ */
.legend { display: flex; flex-wrap: wrap; gap: var(--sop-space-4); align-items: center;
  margin-top: var(--sop-space-4); padding-top: var(--sop-space-3);
  border-top: 1px solid var(--sop-color-border); font-size: var(--sop-text-small);
  color: var(--sop-color-text-secondary); }
.legend__item { display: flex; align-items: center; gap: 7px; }
.legend__swatch { width: 14px; height: 14px; display: inline-block; border-radius: 3px; }

/* --- rail (matches mockups 1+2) --------------------------------------------- */
.rail { display: flex; flex-direction: column; gap: var(--sop-space-4); position: sticky; top: var(--sop-space-4); }
.rail__section { background: var(--sop-color-surface); border: 1px solid var(--sop-color-border);
  border-radius: var(--sop-radius-lg); padding: var(--sop-space-4); }
.rail__label { color: var(--sop-color-text-muted); font-size: var(--sop-text-label);
  text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: var(--sop-space-3); }
.rail__list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: var(--sop-space-3); }
.rail__item { display: flex; gap: 9px; font-size: var(--sop-text-small); line-height: 1.45;
  color: var(--sop-color-text-secondary); }
.rail__item strong { color: var(--sop-color-text-primary); font-weight: 600; }
.dot { width: 8px; height: 8px; border-radius: 50%; flex: none; margin-top: 6px; }
.dot--good { background: var(--sop-color-good); }
.dot--warn { background: var(--sop-color-warn); }
.dot--bad { background: var(--sop-color-bad); }
.dot--info { background: var(--sop-color-info); }
.rail__callout { border-left: 3px solid var(--sop-color-info); background: var(--sop-color-surface-sunken);
  border-radius: var(--sop-radius-sm); padding: var(--sop-space-3); font-size: var(--sop-text-small);
  color: var(--sop-color-text-secondary); }

.foot { margin-top: var(--sop-space-6); padding-top: var(--sop-space-4);
  border-top: 1px solid var(--sop-color-border); color: var(--sop-color-text-muted);
  font-size: var(--sop-text-small); display: flex; gap: var(--sop-space-5); flex-wrap: wrap; }

/* --- tooltip (matches mockup 2) --------------------------------------------- */
.tip { position: fixed; pointer-events: none; z-index: 50; opacity: 0; transition: opacity 90ms linear;
  background: var(--sop-color-surface-raised); border: 1px solid var(--sop-color-border-strong);
  border-radius: var(--sop-radius-md); padding: 10px 12px; font-size: var(--sop-text-small);
  min-width: 180px; max-width: 280px; }
.tip[data-show="1"] { opacity: 1; }
.tip__head { font-weight: 600; margin-bottom: 6px; }
.tip__row { display: flex; justify-content: space-between; gap: var(--sop-space-4);
  color: var(--sop-color-text-secondary); font-variant-numeric: tabular-nums; }
.tip__row b { color: var(--sop-color-text-primary); font-weight: 600; }
.tip__foot { margin-top: 7px; padding-top: 6px; border-top: 1px solid var(--sop-color-border);
  color: var(--sop-color-text-muted); font-size: var(--sop-text-label); }

/* --- provenance modal: layout on top of tokens.css's .modal/.modal-scrim/
   .step-connector base classes (colors/radius/shadow come from there) ------- */
.modal-scrim { position: fixed; inset: 0; z-index: 100; display: none;
  align-items: flex-start; justify-content: center; overflow-y: auto; padding: var(--sop-space-8) var(--sop-space-4); }
.modal-scrim[data-open="1"] { display: flex; }
.modal { position: relative; width: 100%; max-width: 720px; margin: auto 0; }
.modal__close { position: absolute; top: var(--sop-space-4); right: var(--sop-space-4); appearance: none;
  cursor: pointer; background: transparent; border: 1px solid var(--sop-color-border); border-radius: 50%;
  width: 28px; height: 28px; color: var(--sop-color-text-secondary); font-size: 15px; line-height: 1; }
.modal__close:hover { color: var(--sop-color-text-primary); border-color: var(--sop-color-border-strong); }
.modal__eyebrow { font-size: var(--sop-text-label); text-transform: uppercase; letter-spacing: 0.08em;
  color: var(--sop-color-text-muted); margin: 0 0 4px; }
.modal__title { font-size: var(--sop-text-h1); font-weight: 700; margin: 0 0 var(--sop-space-5);
  padding-right: 40px; }
.step { display: flex; gap: var(--sop-space-4); }
.step__rail { display: flex; flex-direction: column; align-items: center; flex: none; }
.step__num { width: 26px; height: 26px; border-radius: 50%; background: var(--sop-color-surface-sunken);
  border: 1px solid var(--sop-color-border-strong); display: flex; align-items: center; justify-content: center;
  font-size: var(--sop-text-small); font-weight: 700; flex: none; }
.step__num--live { border-color: var(--sop-color-brand); color: var(--sop-color-brand); }
.step__num--skip { color: var(--sop-color-text-muted); }
.step:last-of-type .step-connector { display: none; }
.step-connector { flex: 1; min-height: var(--sop-space-4); width: 0; margin: 2px 0; }
.step__body { padding-bottom: var(--sop-space-5); flex: 1; min-width: 0; }
.step__title { font-size: var(--sop-text-body); font-weight: 600; margin: 0 0 4px; }
.step__formula { font-size: var(--sop-text-small); font-variant-numeric: tabular-nums;
  background: var(--sop-color-surface-sunken); border-radius: var(--sop-radius-sm);
  padding: var(--sop-space-2) var(--sop-space-3); margin: 6px 0; line-height: 1.6;
  overflow-x: auto; white-space: normal; word-break: break-word; }
.step__note { font-size: var(--sop-text-small); color: var(--sop-color-text-secondary); margin: 4px 0 0; }
.step__subrow { font-size: var(--sop-text-label); color: var(--sop-color-text-muted); margin-top: 4px; }
.kpi-tieback { margin-top: var(--sop-space-2); border-radius: var(--sop-radius-sm);
  border-left: 3px solid var(--sop-color-brand); background: var(--sop-color-brand-subtle);
  padding: var(--sop-space-3) var(--sop-space-4); }
.kpi-tieback__label { font-size: var(--sop-text-label); text-transform: uppercase; letter-spacing: 0.08em;
  color: var(--sop-color-text-muted); margin: 0 0 4px; }
.kpi-tieback__val { font-size: var(--sop-text-h1); font-weight: 700; font-variant-numeric: tabular-nums; margin: 0; }

@media (max-width: 1180px) {
  .main { grid-template-columns: minmax(0, 1fr); }
  .rail { position: static; }
  .levergroups { grid-template-columns: minmax(0, 1fr); }
}
@media (max-width: 720px) {
  .modal { max-width: 100%; }
}

/* ===== 04-kpi-tiles ===== */

/* =============================================================================
   04-kpi-tiles.html — MOCKUP 4 of 5 (SCOPE.md §9)

   What this mockup is for: the KPI story in one screen — headline decision band,
   then four panels that read live off the 3 locked scenarios (SCOPE §8b):
   fill rate × 3 (bullet graphs), the bottleneck resource's monthly load, margin
   at risk (Dryers, 3 months), upside value (Base → Upside). Drives to the same
   proven rollups + 5-step provenance modal mockup 3 built.

   Redesigned 2026-08-13 after Lavi's rejection of the first hero-tile grid
   ("not very interactive, looks plain AI slop") — presentation rebuilt around
   live panel notes, per-family hover sparklines, a rationing-month sequence
   on the load curve, count-up deltas and a one-authored rise-in moment.
   Kept sound: the data layer, rollup arithmetic, and 5-step modal.

   Every "Why?" traces to real arithmetic, same discipline as mockup 3:
   - Where a KPI IS one family/month's story (Margin at Risk's Dryers
     shortfall), each contributing month is a button that opens the exact
     same 5-step provenance modal mockup 3 built — copied verbatim, not
     reinvented, per HANDOFF's explicit instruction to reuse it.
   - Where a KPI is a genuine aggregate (a fill rate, a resource's 12-month
     utilization curve, a base-vs-upside comparison), a new "rollup" modal
     shows the real per-family or per-month numbers summing to the headline,
     with cross-links into the 5-step modal wherever the rollup bottoms out
     at one real family/month (e.g. the fill-rate-constrained rollup links
     to Dryers' worst month; the bottleneck rollup links to the same cell).
   All numbers are computed client-side from data.js at render time — nothing
   below is a hardcoded figure, same as mockups 1–3.
   ========================================================================== */

*, *::before, *::after { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
body {
  background: var(--sop-color-canvas);
  color: var(--sop-color-text-primary);
  font-family: var(--sop-font-sans);
  font-size: var(--sop-text-body);
  line-height: 1.5;
  -webkit-font-smoothing: antialiased;
}
.page { max-width: 1560px; margin: 0 auto; padding: 0 var(--sop-space-6) var(--sop-space-8); }

/* --- chrome (matches mockups 1–3) ------------------------------------------ */
.topbar { display: flex; align-items: center; gap: var(--sop-space-5);
  padding: var(--sop-space-4) 0; border-bottom: 1px solid var(--sop-color-border); }
.topbar__title { font-size: var(--sop-text-h2); font-weight: 600; margin: 0; letter-spacing: -0.01em; }
.topbar__sub { color: var(--sop-color-text-muted); font-size: var(--sop-text-label);
  text-transform: uppercase; letter-spacing: 0.08em; margin-top: 2px; }
.topbar__spacer { flex: 1; }
.iconbtn { appearance: none; cursor: pointer; font: inherit; font-size: var(--sop-text-small);
  color: var(--sop-color-text-secondary); background: var(--sop-color-surface);
  border: 1px solid var(--sop-color-border); border-radius: var(--sop-radius-md); padding: 6px 12px; }
.iconbtn:hover { color: var(--sop-color-text-primary); border-color: var(--sop-color-border-strong); }

/* --- panels (matches mockups 1–3) ------------------------------------------ */
.main { display: grid; grid-template-columns: minmax(0, 1fr) 340px; gap: var(--sop-space-5);
  align-items: start; padding-top: var(--sop-space-5); }
.stack { display: flex; flex-direction: column; gap: var(--sop-space-5); min-width: 0; }
.panel { background: var(--sop-color-surface); border: 1px solid var(--sop-color-border);
  border-radius: var(--sop-radius-lg); padding: var(--sop-space-5); min-width: 0; }
.panel__head { display: flex; align-items: baseline; gap: var(--sop-space-3);
  margin-bottom: var(--sop-space-4); flex-wrap: wrap; }
.panel__title { font-size: var(--sop-text-h2); font-weight: 600; margin: 0; }
.panel__note { color: var(--sop-color-text-muted); font-size: var(--sop-text-small); margin: 0; }

/* --- tile grid: tokens.css supplies .tile itself, this file only lays out
   the grid and adds the status row + click affordance on top of it ------- */
.tilegrid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--sop-space-4); }
.tile__context { font-size: var(--sop-text-small); color: var(--sop-color-text-secondary); }
.tile[data-clickable] { cursor: default; } /* the tile itself isn't clickable — only .tile__why is, per tokens.css's own affordance */

/* --- rail (matches mockups 1–3) --------------------------------------------- */
.rail { display: flex; flex-direction: column; gap: var(--sop-space-4); position: sticky; top: var(--sop-space-4); }
.rail__section { background: var(--sop-color-surface); border: 1px solid var(--sop-color-border);
  border-radius: var(--sop-radius-lg); padding: var(--sop-space-4); }
.rail__label { color: var(--sop-color-text-muted); font-size: var(--sop-text-label);
  text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: var(--sop-space-3); }
.rail__list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: var(--sop-space-3); }
.rail__item { display: flex; gap: 9px; font-size: var(--sop-text-small); line-height: 1.45;
  color: var(--sop-color-text-secondary); }
.rail__item strong { color: var(--sop-color-text-primary); font-weight: 600; }
.dot { width: 8px; height: 8px; border-radius: 50%; flex: none; margin-top: 6px; }
.dot--good { background: var(--sop-color-good); }
.dot--warn { background: var(--sop-color-warn); }
.dot--bad { background: var(--sop-color-bad); }
.dot--info { background: var(--sop-color-info); }
.rail__callout { border-left: 3px solid var(--sop-color-info); background: var(--sop-color-surface-sunken);
  border-radius: var(--sop-radius-sm); padding: var(--sop-space-3); font-size: var(--sop-text-small);
  color: var(--sop-color-text-secondary); }

.foot { margin-top: var(--sop-space-6); padding-top: var(--sop-space-4);
  border-top: 1px solid var(--sop-color-border); color: var(--sop-color-text-muted);
  font-size: var(--sop-text-small); display: flex; gap: var(--sop-space-5); flex-wrap: wrap; }

/* --- rollup table: same numeric discipline as mockup 3's .dgrid, sized for
   a modal instead of a full-width panel ---------------------------------- */
.rolluptable { width: 100%; border-collapse: collapse; font-size: var(--sop-text-small);
  font-variant-numeric: tabular-nums; margin: var(--sop-space-3) 0; }
.rolluptable th, .rolluptable td { text-align: right; padding: 6px 8px; border-bottom: 1px solid var(--sop-color-border); }
.rolluptable th:first-child, .rolluptable td:first-child { text-align: left; }
.rolluptable thead th { color: var(--sop-color-text-muted); font-size: var(--sop-text-label);
  text-transform: uppercase; letter-spacing: 0.06em; font-weight: 600; border-bottom: 1px solid var(--sop-color-border-strong); }
.rolluptable tbody tr:nth-child(even) { background: var(--sop-table-stripe-bg); }
.rolluptable tr.is-total td { font-weight: 700; border-top: 1px solid var(--sop-color-border-strong); border-bottom: none; }
.rolluptable tr.is-highlight td { background: var(--sop-color-bad-bg); }
.rolluptable .rowbtn { appearance: none; background: transparent; border: 0; padding: 0; cursor: pointer;
  font: inherit; font-variant-numeric: tabular-nums; color: var(--sop-color-info); text-decoration: underline; }
.rollup-formula { font-size: var(--sop-text-small); font-variant-numeric: tabular-nums;
  background: var(--sop-color-surface-sunken); border-radius: var(--sop-radius-sm);
  padding: var(--sop-space-2) var(--sop-space-3); margin: var(--sop-space-3) 0; line-height: 1.6; }
.rollup-note { font-size: var(--sop-text-small); color: var(--sop-color-text-secondary); margin: var(--sop-space-2) 0 0; }
.rollup-link { appearance: none; background: transparent; border: 1px solid var(--sop-color-border);
  border-radius: var(--sop-radius-sm); padding: 6px 10px; margin-top: var(--sop-space-2);
  font: inherit; font-size: var(--sop-text-small); color: var(--sop-color-info); cursor: pointer; }
.rollup-link:hover { border-color: var(--sop-color-border-strong); }

/* --- tooltip (matches mockup 2/3) ------------------------------------------- */
.tip { position: fixed; pointer-events: none; z-index: 50; opacity: 0; transition: opacity 90ms linear;
  background: var(--sop-color-surface-raised); border: 1px solid var(--sop-color-border-strong);
  border-radius: var(--sop-radius-md); padding: 10px 12px; font-size: var(--sop-text-small);
  min-width: 180px; max-width: 280px; }
.tip[data-show="1"] { opacity: 1; }
.tip__head { font-weight: 600; margin-bottom: 6px; }

/* --- modal: identical chrome to mockup 3, reused for both the 5-step
   provenance drill-down AND the new rollups (same .modal/.modal-scrim) --- */
.modal-scrim { position: fixed; inset: 0; z-index: 100; display: none;
  align-items: flex-start; justify-content: center; overflow-y: auto; padding: var(--sop-space-8) var(--sop-space-4); }
.modal-scrim[data-open="1"] { display: flex; }
.modal { position: relative; width: 100%; max-width: 720px; margin: auto 0; }
.modal__close { position: absolute; top: var(--sop-space-4); right: var(--sop-space-4); appearance: none;
  cursor: pointer; background: transparent; border: 1px solid var(--sop-color-border); border-radius: 50%;
  width: 28px; height: 28px; color: var(--sop-color-text-secondary); font-size: 15px; line-height: 1; }
.modal__close:hover { color: var(--sop-color-text-primary); border-color: var(--sop-color-border-strong); }
.modal__eyebrow { font-size: var(--sop-text-label); text-transform: uppercase; letter-spacing: 0.08em;
  color: var(--sop-color-text-muted); margin: 0 0 4px; }
.modal__title { font-size: var(--sop-text-h1); font-weight: 700; margin: 0 0 var(--sop-space-5);
  padding-right: 40px; }
.step { display: flex; gap: var(--sop-space-4); }
.step__rail { display: flex; flex-direction: column; align-items: center; flex: none; }
.step__num { width: 26px; height: 26px; border-radius: 50%; background: var(--sop-color-surface-sunken);
  border: 1px solid var(--sop-color-border-strong); display: flex; align-items: center; justify-content: center;
  font-size: var(--sop-text-small); font-weight: 700; flex: none; }
.step__num--live { border-color: var(--sop-color-brand); color: var(--sop-color-brand); }
.step__num--skip { color: var(--sop-color-text-muted); }
.step:last-of-type .step-connector { display: none; }
.step-connector { flex: 1; min-height: var(--sop-space-4); width: 0; margin: 2px 0; }
.step__body { padding-bottom: var(--sop-space-5); flex: 1; min-width: 0; }
.step__title { font-size: var(--sop-text-body); font-weight: 600; margin: 0 0 4px; }
.step__formula { font-size: var(--sop-text-small); font-variant-numeric: tabular-nums;
  background: var(--sop-color-surface-sunken); border-radius: var(--sop-radius-sm);
  padding: var(--sop-space-2) var(--sop-space-3); margin: 6px 0; line-height: 1.6;
  overflow-x: auto; white-space: normal; word-break: break-word; }
.step__note { font-size: var(--sop-text-small); color: var(--sop-color-text-secondary); margin: 4px 0 0; }
.kpi-tieback { margin-top: var(--sop-space-2); border-radius: var(--sop-radius-sm);
  border-left: 3px solid var(--sop-color-brand); background: var(--sop-color-brand-subtle);
  padding: var(--sop-space-3) var(--sop-space-4); }
.kpi-tieback__label { font-size: var(--sop-text-label); text-transform: uppercase; letter-spacing: 0.08em;
  color: var(--sop-color-text-muted); margin: 0 0 4px; }
.kpi-tieback__val { font-size: var(--sop-text-h1); font-weight: 700; font-variant-numeric: tabular-nums; margin: 0; }

@media (max-width: 1180px) {
  .main { grid-template-columns: minmax(0, 1fr); }
  .rail { position: static; }
}
@media (max-width: 900px) {
  .duo { grid-template-columns: 1fr; }
  .fillrow { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 640px) {
  .fillrow { grid-template-columns: 1fr; }
  .headline__top { grid-template-columns: 1fr; }
}
@media (max-width: 720px) {
  .modal { max-width: 100%; }
}

/* --- chart helpers (copied from mockup 02-scenario-comparison.html) -------- */
.bar-label { fill: var(--sop-color-text-secondary); font-size: 10px; font-family: var(--sop-font-sans); }
.bar-value { fill: var(--sop-color-text-primary); font-size: 10px; font-weight: 600;
  font-family: var(--sop-font-sans); }
.tick-text { fill: var(--sop-color-text-muted); font-size: 9px; font-family: var(--sop-font-sans); }
.axis-line { stroke: var(--sop-color-chart-axis); stroke-width: 1; }
.ref-line { stroke: var(--sop-color-text-muted); stroke-width: 1; stroke-dasharray: 3 3; }
.mark-hit { fill: transparent; cursor: pointer; }

/* --- bullet graphs -------------------------------------------------------- */
.bullets { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--sop-space-5); }
.bullet { min-width: 0; }
.bullet__head { display: flex; align-items: baseline; justify-content: space-between; gap: var(--sop-space-3); }
.bullet__name { font-size: var(--sop-text-small); font-weight: 600; }
.bullet__sub { color: var(--sop-color-text-muted); font-size: var(--sop-text-label); }
.bullet svg { display: block; width: 100%; height: auto; margin-top: 6px; }

.bandkey { display: flex; gap: var(--sop-space-4); flex-wrap: wrap; margin-top: var(--sop-space-4);
  padding-top: var(--sop-space-3); border-top: 1px solid var(--sop-color-border);
  font-size: var(--sop-text-small); color: var(--sop-color-text-secondary); }
.bandkey__item { display: flex; align-items: center; gap: 7px; }
.bandkey__swatch { width: 20px; height: 11px; display: inline-block; border-radius: 2px; }

/* --- legend --------------------------------------------------------------- */
.legend { display: flex; flex-wrap: wrap; gap: var(--sop-space-4); align-items: center;
  margin-top: var(--sop-space-4); padding-top: var(--sop-space-3);
  border-top: 1px solid var(--sop-color-border); font-size: var(--sop-text-small);
  color: var(--sop-color-text-secondary); }
.legend__item { display: flex; align-items: center; gap: 7px; }
.legend__swatch { width: 20px; height: 11px; display: inline-block; }

.delta { font-variant-numeric: tabular-nums; font-weight: 600; }
.delta--good { color: var(--sop-color-good); }
.delta--bad { color: var(--sop-color-bad); }
.delta--flat { color: var(--sop-color-text-muted); }

/* --- mockup-4 chart panels (IBCS, SCOPE §8b) ------------------------------- */
.fillrow { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--sop-space-5); }
.duo { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--sop-space-5); }
.chartwrap { min-width: 0; cursor: pointer; }
.chartwrap svg { display: block; width: 100%; height: auto; }
.bullet.clickable { cursor: pointer; }
.chartnote { font-size: var(--sop-text-small); color: var(--sop-color-text-secondary);
  margin: var(--sop-space-3) 0 0; line-height: 1.7; }

/* --- headline band — the 5-second decision (SCOPE §8b) --------------------- */
.panel--headline { padding: var(--sop-space-5) var(--sop-space-6); }
.headline__top { display: grid; grid-template-columns: 1fr 1fr; gap: var(--sop-space-6); }
.headline__kicker { display: block; font-size: var(--sop-text-label); text-transform: uppercase;
  letter-spacing: 0.08em; color: var(--sop-color-text-muted); margin-bottom: 6px; }
.headline__lede { font-size: var(--sop-text-body); line-height: 1.5; margin: 0; }
.headline__lede strong { font-weight: 700; }
.headline__trade { margin-top: var(--sop-space-4); padding-top: var(--sop-space-3);
  border-top: 1px solid var(--sop-color-border); font-size: var(--sop-text-small);
  color: var(--sop-color-text-secondary); line-height: 1.7; }

/* --- live verdict notes (the panel note becomes the story, not a legend) --- */
.panel__note b, .panel__note strong { color: var(--sop-color-text-primary); font-weight: var(--sop-weight-semibold); }
.panel__note .delta { font-weight: var(--sop-weight-semibold); }
.panel__note .delta--good { color: var(--sop-color-good); }
.panel__note .delta--bad { color: var(--sop-color-bad); }
.panel__note .delta--flat { color: var(--sop-color-text-muted); }

/* --- number count-up: tabular numerals keep the grid from jittering while
   the delta animates to its final figure on first view --------------------- */
.num-anim { display: inline-block; font-variant-numeric: tabular-nums; font-feature-settings: var(--sop-font-feature-tabular); }

/* --- explicit drill affordance: the whole panel already clicks; this link
   says so and shows where it goes, instead of relying on an invisible
   click-target + a tooltip nobody discovers -------------------------------- */
.drill { display: inline-flex; align-items: center; gap: 6px; margin-top: var(--sop-space-2);
  appearance: none; background: transparent; border: 0; padding: 0; cursor: pointer;
  font-family: inherit; font-size: var(--sop-text-small); font-weight: var(--sop-weight-semibold);
  color: var(--sop-color-info); }
.drill .drill__arrow { transition: transform 120ms ease-out; }
.drill:hover .drill__arrow { transform: translateX(3px); }

/* --- load-curve flag chips: the rationing months rise out of the axis so
   the sequence (3 months that actually cost shipped units) is scannable --- */
.mflag { font-size: 9px; font-weight: var(--sop-weight-semibold); letter-spacing: 0.04em; }
.mflag--ration { fill: var(--sop-color-bad); }
.mflag--ration.track { fill: var(--sop-color-bad-bg); }
.mflag--label { fill: var(--sop-color-text-secondary); font-weight: var(--sop-weight-regular); }

/* --- fill-tile corner popover: a real 12-month sparkline per family appears
   on hover — data already exists, so this is depth, not decoration ---------- */
.fillpop { position: absolute; z-index: 60; pointer-events: none; opacity: 0; transition: opacity 110ms ease;
  background: var(--sop-color-surface-raised); border: 1px solid var(--sop-color-border-strong);
  border-radius: var(--sop-radius-md); padding: var(--sop-space-3); width: 216px; }
.fillpop[data-show="1"] { opacity: 1; }
.fillpop__head { font-size: var(--sop-text-label); text-transform: uppercase; letter-spacing: var(--sop-label-tracking);
  color: var(--sop-color-text-muted); margin: 0 0 6px; font-weight: var(--sop-weight-semibold); }
.fillpop svg { display: block; width: 100%; height: 34px; }
.bullet { position: relative; }
.bullet.clickable { cursor: pointer; }

/* --- margin-bar entrance: the three bars rise from baseline in sequence on
   first view — one authored moment, not scattered effects ------------------- */
@keyframes riseIn {
  from { transform: scaleY(0); }
  to   { transform: scaleY(1); }
}
.rise { transform-origin: bottom; animation: riseIn 520ms cubic-bezier(0.22, 1, 0.36, 1) both; }
.rise--1 { animation-delay: 60ms; }
.rise--2 { animation-delay: 160ms; }
.rise--3 { animation-delay: 260ms; }

/* ===== 05-margin-waterfall ===== */

/* =============================================================================
   05-margin-waterfall.html — MOCKUP 5 of 5 (SCOPE.md §9)

   What this mockup is for: the margin waterfall (SCOPE §8b chart grammar) — vertical bridge from Base to Realized. (DESIGN.md §2's candidate list,
   read as a starting point per HANDOFF-sop-revamp.md, not gospel). Reuses
   tokens.css's pre-built .tile anatomy verbatim — label row with info
   affordance, hero number, delta row, "Why?" drill-in link — rather than
   inventing new tile markup.

   Six tiles: Fill Rate × 3 (Base/Upside/Constrained), Bottleneck Resource
   Utilization, Upside Value Unlocked, Margin at Risk (Constrained). No
   scenario tabs here — unlike mockups 1–3, the tile row's whole point is
   showing all 3 scenarios at a glance with zero navigation (SCOPE §6b's
   "three lenses on one canvas" pattern), so each tile names its own scenario.

   Every "Why?" traces to real arithmetic, same discipline as mockup 3:
   - Where a KPI IS one family/month's story (Margin at Risk's Dryers
     shortfall), each contributing month is a button that opens the exact
     same 5-step provenance modal mockup 3 built — copied verbatim, not
     reinvented, per HANDOFF's explicit instruction to reuse it.
   - Where a KPI is a genuine aggregate (a fill rate, a resource's 12-month
     utilization curve, a base-vs-upside comparison), a new "rollup" modal
     shows the real per-family or per-month numbers summing to the headline,
     with cross-links into the 5-step modal wherever the rollup bottoms out
     at one real family/month (e.g. the fill-rate-constrained rollup links
     to Dryers' worst month; the bottleneck rollup links to the same cell).
   All numbers are computed client-side from data.js at render time — nothing
   below is a hardcoded figure, same as mockups 1–3.
   ========================================================================== */

*, *::before, *::after { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
body {
  background: var(--sop-color-canvas);
  color: var(--sop-color-text-primary);
  font-family: var(--sop-font-sans);
  font-size: var(--sop-text-body);
  line-height: 1.5;
  -webkit-font-smoothing: antialiased;
}
.page { max-width: 1560px; margin: 0 auto; padding: 0 var(--sop-space-6) var(--sop-space-8); }

/* --- chrome (matches mockups 1–3) ------------------------------------------ */
.topbar { display: flex; align-items: center; gap: var(--sop-space-5);
  padding: var(--sop-space-4) 0; border-bottom: 1px solid var(--sop-color-border); }
.topbar__title { font-size: var(--sop-text-h2); font-weight: 600; margin: 0; letter-spacing: -0.01em; }
.topbar__sub { color: var(--sop-color-text-muted); font-size: var(--sop-text-label);
  text-transform: uppercase; letter-spacing: 0.08em; margin-top: 2px; }
.topbar__spacer { flex: 1; }
.iconbtn { appearance: none; cursor: pointer; font: inherit; font-size: var(--sop-text-small);
  color: var(--sop-color-text-secondary); background: var(--sop-color-surface);
  border: 1px solid var(--sop-color-border); border-radius: var(--sop-radius-md); padding: 6px 12px; }
.iconbtn:hover { color: var(--sop-color-text-primary); border-color: var(--sop-color-border-strong); }

/* --- panels (matches mockups 1–3) ------------------------------------------ */
.main { display: grid; grid-template-columns: minmax(0, 1fr) 340px; gap: var(--sop-space-5);
  align-items: start; padding-top: var(--sop-space-5); }
.stack { display: flex; flex-direction: column; gap: var(--sop-space-5); min-width: 0; }
.panel { background: var(--sop-color-surface); border: 1px solid var(--sop-color-border);
  border-radius: var(--sop-radius-lg); padding: var(--sop-space-5); min-width: 0; }
.panel__head { display: flex; align-items: baseline; gap: var(--sop-space-3);
  margin-bottom: var(--sop-space-4); flex-wrap: wrap; }
.panel__title { font-size: var(--sop-text-h2); font-weight: 600; margin: 0; }
.panel__note { color: var(--sop-color-text-muted); font-size: var(--sop-text-small); margin: 0; }

/* --- tile grid: tokens.css supplies .tile itself, this file only lays out
   the grid and adds the status row + click affordance on top of it ------- */
.tile__context { font-size: var(--sop-text-small); color: var(--sop-color-text-secondary); }
.tile[data-clickable] { cursor: default; } /* the tile itself isn't clickable — only .tile__why is, per tokens.css's own affordance */

/* --- rail (matches mockups 1–3) --------------------------------------------- */
.rail { display: flex; flex-direction: column; gap: var(--sop-space-4); position: sticky; top: var(--sop-space-4); }
.rail__section { background: var(--sop-color-surface); border: 1px solid var(--sop-color-border);
  border-radius: var(--sop-radius-lg); padding: var(--sop-space-4); }
.rail__label { color: var(--sop-color-text-muted); font-size: var(--sop-text-label);
  text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: var(--sop-space-3); }
.rail__list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: var(--sop-space-3); }
.rail__item { display: flex; gap: 9px; font-size: var(--sop-text-small); line-height: 1.45;
  color: var(--sop-color-text-secondary); }
.rail__item strong { color: var(--sop-color-text-primary); font-weight: 600; }
.dot { width: 8px; height: 8px; border-radius: 50%; flex: none; margin-top: 6px; }
.dot--good { background: var(--sop-color-good); }
.dot--warn { background: var(--sop-color-warn); }
.dot--bad { background: var(--sop-color-bad); }
.dot--info { background: var(--sop-color-info); }
.rail__callout { border-left: 3px solid var(--sop-color-info); background: var(--sop-color-surface-sunken);
  border-radius: var(--sop-radius-sm); padding: var(--sop-space-3); font-size: var(--sop-text-small);
  color: var(--sop-color-text-secondary); }

.foot { margin-top: var(--sop-space-6); padding-top: var(--sop-space-4);
  border-top: 1px solid var(--sop-color-border); color: var(--sop-color-text-muted);
  font-size: var(--sop-text-small); display: flex; gap: var(--sop-space-5); flex-wrap: wrap; }

/* --- rollup table: same numeric discipline as mockup 3's .dgrid, sized for
   a modal instead of a full-width panel ---------------------------------- */
.rolluptable { width: 100%; border-collapse: collapse; font-size: var(--sop-text-small);
  font-variant-numeric: tabular-nums; margin: var(--sop-space-3) 0; }
.rolluptable th, .rolluptable td { text-align: right; padding: 6px 8px; border-bottom: 1px solid var(--sop-color-border); }
.rolluptable th:first-child, .rolluptable td:first-child { text-align: left; }
.rolluptable thead th { color: var(--sop-color-text-muted); font-size: var(--sop-text-label);
  text-transform: uppercase; letter-spacing: 0.06em; font-weight: 600; border-bottom: 1px solid var(--sop-color-border-strong); }
.rolluptable tbody tr:nth-child(even) { background: var(--sop-table-stripe-bg); }
.rolluptable tr.is-total td { font-weight: 700; border-top: 1px solid var(--sop-color-border-strong); border-bottom: none; }
.rolluptable tr.is-highlight td { background: var(--sop-color-bad-bg); }
.rolluptable .rowbtn { appearance: none; background: transparent; border: 0; padding: 0; cursor: pointer;
  font: inherit; font-variant-numeric: tabular-nums; color: var(--sop-color-info); text-decoration: underline; }
.rollup-formula { font-size: var(--sop-text-small); font-variant-numeric: tabular-nums;
  background: var(--sop-color-surface-sunken); border-radius: var(--sop-radius-sm);
  padding: var(--sop-space-2) var(--sop-space-3); margin: var(--sop-space-3) 0; line-height: 1.6; }
.rollup-note { font-size: var(--sop-text-small); color: var(--sop-color-text-secondary); margin: var(--sop-space-2) 0 0; }
.rollup-link { appearance: none; background: transparent; border: 1px solid var(--sop-color-border);
  border-radius: var(--sop-radius-sm); padding: 6px 10px; margin-top: var(--sop-space-2);
  font: inherit; font-size: var(--sop-text-small); color: var(--sop-color-info); cursor: pointer; }
.rollup-link:hover { border-color: var(--sop-color-border-strong); }

/* --- tooltip (matches mockup 2/3) ------------------------------------------- */
.tip { position: fixed; pointer-events: none; z-index: 50; opacity: 0; transition: opacity 90ms linear;
  background: var(--sop-color-surface-raised); border: 1px solid var(--sop-color-border-strong);
  border-radius: var(--sop-radius-md); padding: 10px 12px; font-size: var(--sop-text-small);
  min-width: 180px; max-width: 280px; }
.tip[data-show="1"] { opacity: 1; }
.tip__head { font-weight: 600; margin-bottom: 6px; }

/* --- modal: identical chrome to mockup 3, reused for both the 5-step
   provenance drill-down AND the new rollups (same .modal/.modal-scrim) --- */
.modal-scrim { position: fixed; inset: 0; z-index: 100; display: none;
  align-items: flex-start; justify-content: center; overflow-y: auto; padding: var(--sop-space-8) var(--sop-space-4); }
.modal-scrim[data-open="1"] { display: flex; }
.modal { position: relative; width: 100%; max-width: 720px; margin: auto 0; }
.modal__close { position: absolute; top: var(--sop-space-4); right: var(--sop-space-4); appearance: none;
  cursor: pointer; background: transparent; border: 1px solid var(--sop-color-border); border-radius: 50%;
  width: 28px; height: 28px; color: var(--sop-color-text-secondary); font-size: 15px; line-height: 1; }
.modal__close:hover { color: var(--sop-color-text-primary); border-color: var(--sop-color-border-strong); }
.modal__eyebrow { font-size: var(--sop-text-label); text-transform: uppercase; letter-spacing: 0.08em;
  color: var(--sop-color-text-muted); margin: 0 0 4px; }
.modal__title { font-size: var(--sop-text-h1); font-weight: 700; margin: 0 0 var(--sop-space-5);
  padding-right: 40px; }
.step { display: flex; gap: var(--sop-space-4); }
.step__rail { display: flex; flex-direction: column; align-items: center; flex: none; }
.step__num { width: 26px; height: 26px; border-radius: 50%; background: var(--sop-color-surface-sunken);
  border: 1px solid var(--sop-color-border-strong); display: flex; align-items: center; justify-content: center;
  font-size: var(--sop-text-small); font-weight: 700; flex: none; }
.step__num--live { border-color: var(--sop-color-brand); color: var(--sop-color-brand); }
.step__num--skip { color: var(--sop-color-text-muted); }
.step:last-of-type .step-connector { display: none; }
.step-connector { flex: 1; min-height: var(--sop-space-4); width: 0; margin: 2px 0; }
.step__body { padding-bottom: var(--sop-space-5); flex: 1; min-width: 0; }
.step__title { font-size: var(--sop-text-body); font-weight: 600; margin: 0 0 4px; }
.step__formula { font-size: var(--sop-text-small); font-variant-numeric: tabular-nums;
  background: var(--sop-color-surface-sunken); border-radius: var(--sop-radius-sm);
  padding: var(--sop-space-2) var(--sop-space-3); margin: 6px 0; line-height: 1.6;
  overflow-x: auto; white-space: normal; word-break: break-word; }
.step__note { font-size: var(--sop-text-small); color: var(--sop-color-text-secondary); margin: 4px 0 0; }
.kpi-tieback { margin-top: var(--sop-space-2); border-radius: var(--sop-radius-sm);
  border-left: 3px solid var(--sop-color-brand); background: var(--sop-color-brand-subtle);
  padding: var(--sop-space-3) var(--sop-space-4); }
.kpi-tieback__label { font-size: var(--sop-text-label); text-transform: uppercase; letter-spacing: 0.08em;
  color: var(--sop-color-text-muted); margin: 0 0 4px; }
.kpi-tieback__val { font-size: var(--sop-text-h1); font-weight: 700; font-variant-numeric: tabular-nums; margin: 0; }

@media (max-width: 1180px) {
  .main { grid-template-columns: minmax(0, 1fr); }
  .rail { position: static; }
}
@media (max-width: 900px) {
}
@media (max-width: 640px) {
  .headline__top { grid-template-columns: 1fr; }
}
@media (max-width: 720px) {
  .modal { max-width: 100%; }
}

/* --- chart helpers (copied from mockup 02-scenario-comparison.html) -------- */
.bar-label { fill: var(--sop-color-text-secondary); font-size: 10px; font-family: var(--sop-font-sans); }
.bar-value { fill: var(--sop-color-text-primary); font-size: 10px; font-weight: 600;
  font-family: var(--sop-font-sans); }
.tick-text { fill: var(--sop-color-text-muted); font-size: 9px; font-family: var(--sop-font-sans); }
.axis-line { stroke: var(--sop-color-chart-axis); stroke-width: 1; }
.ref-line { stroke: var(--sop-color-text-muted); stroke-width: 1; stroke-dasharray: 3 3; }
.mark-hit { fill: transparent; cursor: pointer; }

.bandkey { display: flex; gap: var(--sop-space-4); flex-wrap: wrap; margin-top: var(--sop-space-4);
  padding-top: var(--sop-space-3); border-top: 1px solid var(--sop-color-border);
  font-size: var(--sop-text-small); color: var(--sop-color-text-secondary); }
.bandkey__item { display: flex; align-items: center; gap: 7px; }
.bandkey__swatch { width: 20px; height: 11px; display: inline-block; border-radius: 2px; }

/* --- legend --------------------------------------------------------------- */
.legend { display: flex; flex-wrap: wrap; gap: var(--sop-space-4); align-items: center;
  margin-top: var(--sop-space-4); padding-top: var(--sop-space-3);
  border-top: 1px solid var(--sop-color-border); font-size: var(--sop-text-small);
  color: var(--sop-color-text-secondary); }
.legend__item { display: flex; align-items: center; gap: 7px; }
.legend__swatch { width: 20px; height: 11px; display: inline-block; }

.delta { font-variant-numeric: tabular-nums; font-weight: 600; }
.delta--good { color: var(--sop-color-good); }
.delta--bad { color: var(--sop-color-bad); }
.delta--flat { color: var(--sop-color-text-muted); }

.chartnote { font-size: var(--sop-text-small); color: var(--sop-color-text-secondary);
  margin: var(--sop-space-3) 0 0; line-height: 1.7; }

/* --- headline band — the 5-second decision (SCOPE §8b) --------------------- */
.panel--headline { padding: var(--sop-space-5) var(--sop-space-6); }
.headline__top { display: grid; grid-template-columns: 1fr 1fr; gap: var(--sop-space-6); }
.headline__kicker { display: block; font-size: var(--sop-text-label); text-transform: uppercase;
  letter-spacing: 0.08em; color: var(--sop-color-text-muted); margin-bottom: 6px; }
.headline__lede { font-size: var(--sop-text-body); line-height: 1.5; margin: 0; }
.headline__lede strong { font-weight: 700; }
.headline__trade { margin-top: var(--sop-space-4); padding-top: var(--sop-space-3);
  border-top: 1px solid var(--sop-color-border); font-size: var(--sop-text-small);
  color: var(--sop-color-text-secondary); line-height: 1.7; }

/* ============================ MOCKUP 5 WATERFALL ========================= */
/* Vertical margin waterfall (SCOPE §8b): base → +upside lift → −constrained
   penalty → realized. IBCS notation: ink = actual; good/bad hues carry the
   deltas; variance always shows a ▲/▼ glyph, never hue alone. */
.wf { display: grid; grid-template-columns: minmax(0, 1fr) 320px; gap: var(--sop-space-5); align-items: start; }
.wf__chart { background: var(--sop-color-surface-sunken); border-radius: var(--sop-radius-lg); padding: var(--sop-space-5) var(--sop-space-5) var(--sop-space-3); }
.wf__svg { width: 100%; height: auto; display: block; }
.wf__axislabel { fill: var(--sop-color-text-muted); font: 11px var(--sop-font-sans); letter-spacing: 0.02em; }
.wf__steplabel { fill: var(--sop-color-text-secondary); font: 12px var(--sop-font-sans); }
.wf__stepval { fill: var(--sop-color-text-primary); font: 700 12px var(--sop-font-sans); }
.wf__delta { fill: var(--sop-color-text-primary); font: 700 12px var(--sop-font-sans); }
.wf__delta--bad { fill: var(--sop-color-text-primary); font: 700 12px var(--sop-font-sans); }
.wf__label-on-bar { fill: #ffffff; font: 700 12px var(--sop-font-sans); paint-order: stroke; stroke: rgba(0,0,0,0.35); stroke-width: 3px; stroke-linejoin: round; }
.wf__label-on-light { fill: #14161c; font: 700 12px var(--sop-font-sans); }
.wf__label-on-badge { fill: var(--sop-color-text-primary); font: 700 12px var(--sop-font-sans); }
.wf__badge { fill: var(--sop-color-surface-raised); stroke: var(--sop-color-border); }
.wf__connector { stroke: var(--sop-color-border-strong); stroke-width: 1; stroke-dasharray: 3 3; }
.wf__baseline { stroke: var(--sop-color-chart-axis); stroke-width: 1; }
.wf__hdr { display:flex; align-items:baseline; justify-content:space-between; gap: var(--sop-space-3); }
.wf__hdr .panel__title { font-size: var(--sop-text-h2); }
.wf__kicker { color: var(--sop-color-text-muted); font: 11px var(--sop-font-sans); text-transform: uppercase; letter-spacing: 0.08em; }
.wf__lede { font: 600 var(--sop-text-body) var(--sop-font-sans); color: var(--sop-color-text-primary); margin: 2px 0 0; }
.wf__note { color: var(--sop-color-text-muted); font-size: var(--sop-text-small); margin: 0; }
.wf__table { width: 100%; border-collapse: collapse; font-size: var(--sop-text-small); }
.wf__table th, .wf__table td { text-align: right; padding: 5px 8px; border-bottom: 1px solid var(--sop-color-border); }
.wf__table th:first-child, .wf__table td:first-child { text-align: left; }
.wf__table th { color: var(--sop-color-text-muted); text-transform: uppercase; letter-spacing: 0.06em; font-size: 10px; font-weight: 600; }
.wf__table td { font-variant-numeric: tabular-nums; }
.wf__table tbody tr:last-child td { border-bottom: 0; }
.wf__table .is-total td { font-weight: 600; border-top: 2px solid var(--sop-color-border-strong); color: var(--sop-color-text-primary); }
.wf__val-good { color: var(--sop-color-good); }
.wf__val-bad { color: var(--sop-color-bad); }
.wf__cellclick { cursor: pointer; text-decoration: underline; text-underline-offset: 2px; text-decoration-style: dotted; }
.wf__cellclick:hover { color: var(--sop-color-info); }
.wf__legend { display: flex; gap: var(--sop-space-4); flex-wrap: wrap; margin-top: var(--sop-space-2); }
.wf__legend span { display: inline-flex; align-items: center; gap: 6px; font-size: var(--sop-text-small); color: var(--sop-color-text-secondary); }
.wf__swatch { width: 12px; height: 12px; border-radius: 2px; display: inline-block; }
.wf__swatch--base { background: var(--sop-color-ink); }
.wf__swatch--up { background: var(--sop-color-good); }
.wf__swatch--pen { background: var(--sop-color-bad); }
.wf__swatch--real { background: var(--sop-color-info); }


</style>
</head>
<body>
<!-- SVG defs: forecast/constrained hatch. Scenario identity is PATTERN, not hue. -->
<svg width="0" height="0" aria-hidden="true" style="position:absolute">
  <defs>
    <pattern id="hatch" width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
      <rect width="5" height="5" fill="none"></rect>
      <line x1="0" y1="0" x2="0" y2="5" stroke="var(--sop-color-ink-soft)" stroke-width="2.2"></line>
    </pattern>
  </defs>
</svg>

<div class="page">

  <header class="topbar">
    <div>
      <h1 class="topbar__title" id="co">S&amp;OP Cockpit</h1>
      <div class="topbar__sub" id="cycle">Annual plan · 12 monthly buckets</div>
    </div>
    <div class="topbar__spacer"></div>
    <button class="iconbtn" id="tabletoggle" aria-expanded="false">Show table</button>
    <button class="iconbtn" id="themetoggle">Light</button>
  </header>

  <!-- 5-second read: what to do, and what stops us -->
  <section class="panel panel--headline" id="headline"></section>

  <section class="tiles" id="tiles"></section>

  <div class="main">

    <div class="stack">

      <!-- Scenario presets (SCOPE §3) -->
      <section class="panel">
        <div class="panel__head">
          <h2 class="panel__title">Scenarios</h2>
          <p class="panel__note">Four anchor presets; a user-built scenario is a named delta from Base (SCOPE §3).</p>
        </div>
        <div class="presets" id="presets" aria-label="Scenario presets"></div>
      </section>

      <!-- Small multiples: demand vs shipped, revenue, bottleneck load (m1) -->
      <section class="panel">
        <div class="panel__head">
          <h2 class="panel__title">Demand vs shipped — shared scale</h2>
          <p class="panel__note">Rows are metrics, columns are scenarios. Each row shares one y-scale across all three columns, so heights are directly comparable.</p>
        </div>
        <div class="sm" id="sm"></div>
        <div class="legend" id="legend"></div>

        <div class="tablewrap" id="tablewrap" hidden>
          <table id="table"></table>
        </div>
      </section>

      <!-- Structural comparison + bullets + families (m2) -->
      <section class="panel">
        <div class="panel__head">
          <h2 class="panel__title">Structural comparison</h2>
          <p class="panel__note">Levels on the left, variance vs Base on the right — never levels alone. One shared scale per metric; horizontal bars, because vertical columns are reserved for time series.</p>
        </div>
        <div class="cmp" id="cmp"></div>
      </section>

      <section class="panel">
        <div class="panel__head">
          <h2 class="panel__title">Where the plan is tight</h2>
          <p class="panel__note">Bullet graphs against a derived reference, not a business target — Stage-4 targets do not exist in the data yet.</p>
        </div>
        <div class="bullets" id="bullets"></div>
        <div class="bandkey" id="bandkey"></div>
      </section>

      <section class="panel">
        <div class="panel__head">
          <h2 class="panel__title">Where the margin actually moves</h2>
          <p class="panel__note" id="famnote">Gross margin by family, and what rationing takes off it.</p>
        </div>
        <div class="cmp" id="fam"></div>
      </section>

      <!-- Levers (m3) -->
      <section class="panel">
        <div class="panel__head">
          <h2 class="panel__title">Levers</h2>
          <p class="panel__note">Tier 1 on the panel by default (SCOPE §4); Tier 2 sits behind Advanced — comprehensive underneath, calm on first render.</p>
        </div>
        <div class="leverpanel__banner">
          <span>⚡</span>
          <span><b>Live.</b> Drag a lever to recompute the scenario client-side — no Python round-trip (SCOPE §2 row 7). The custom scenario replaces the focused column; every number is the same engine arithmetic, re-run in your browser.</span>
        </div>
        <div class="levergroups" id="levergroups"></div>
        <details class="advanced">
          <summary>Advanced (Tier 2)</summary>
          <div class="advanced__body">
            <div class="levergroups" id="levergroups2"></div>
          </div>
        </details>
      </section>

      <!-- Drill-down grid (m3) -->
      <section class="panel">
        <div class="panel__head">
          <h2 class="panel__title">Click any number, see how it was made</h2>
          <p class="panel__note" id="gridnote">Fill rate by family and month. Every cell drills to its real Demand → Capacity → Rationing → Supply → Financials arithmetic.</p>
        </div>
        <div class="scenariotabs" id="scenariotabs" aria-label="Scenario"></div>
        <div style="overflow-x:auto;">
          <table class="dgrid" id="grid"></table>
        </div>
        <div class="legend" id="legend-drill"></div>
      </section>

      <!-- KPI panels (m4) -->
      <section class="panel">
        <div class="panel__head">
          <h2 class="panel__title">Fill rate · three scenarios</h2>
          <p class="panel__note" id="fillnote"></p>
        </div>
        <div class="fillrow" id="fillrow"></div>
      </section>

      <section class="panel">
        <div class="panel__head">
          <h2 class="panel__title">Bottleneck resource · monthly load</h2>
          <p class="panel__note" id="loadnote"></p>
        </div>
        <div class="chartwrap" id="loadwrap"></div>
      </section>

      <div class="duo">
        <section class="panel">
          <div class="panel__head">
            <h2 class="panel__title">Margin at risk · Constrained</h2>
            <p class="panel__note" id="marginnote"></p>
          </div>
          <div class="chartwrap" id="marginwrap"></div>
          <button type="button" class="drill" id="margindrill"><span>Dryers, 3 months of the year</span><span class="drill__arrow">→</span></button>
        </section>
        <section class="panel">
          <div class="panel__head">
            <h2 class="panel__title">Upside value · Base → Upside</h2>
            <p class="panel__note" id="upsidenote"></p>
          </div>
          <div class="chartwrap" id="upsidewrap"></div>
          <button type="button" class="drill" id="upsidedrill"><span>Open the family-by-family rollup</span><span class="drill__arrow">→</span></button>
        </section>
      </div>

      <!-- Margin waterfall + bridge (m5) -->
      <section class="panel" id="wfpanel">
        <div class="panel__head wf__hdr">
          <h2 class="panel__title">Margin bridge — how the recommended plan's gross margin is reached</h2>
          <p class="panel__note">Base → +upside lift → −constrained penalty → realized. Every bar is a real figure from the engine; click any bar for the rollup, or a row in the table.</p>
        </div>
        <div class="wf__chart"><svg class="wf__svg" id="wfsvg" viewBox="0 0 760 300" role="img" aria-label="Margin waterfall: base, upside lift, constrained penalty, realized"></svg></div>
        <div class="wf__legend">
          <span><span class="wf__swatch wf__swatch--base"></span>Base margin (actual)</span>
          <span><span class="wf__swatch wf__swatch--up"></span>Upside lift (▲)</span>
          <span><span class="wf__swatch wf__swatch--pen"></span>Constrained penalty (▼)</span>
          <span><span class="wf__swatch wf__swatch--real"></span>Realized — Constrained</span>
        </div>
      </section>

      <section class="panel" id="bridgepanel">
        <div class="panel__head">
          <h2 class="panel__title">Bridge — the same four numbers, tabular</h2>
          <p class="panel__note">Complex structures collapse to a table. The waterfall above and this table are the same arithmetic — trace it either way.</p>
        </div>
        <table class="wf__table" id="bridgetable">
          <thead><tr><th>Step</th><th>Value</th><th>Rollup →</th></tr></thead>
          <tbody></tbody>
        </table>
      </section>

    </div>

    <aside class="rail">
      <section class="rail__section">
        <div class="rail__label">What the plan says</div>
        <ul class="rail__list" id="findings"></ul>
      </section>
      <section class="rail__section">
        <div class="rail__label">Assumptions in force</div>
        <div class="rail__callout" id="assumptions"></div>
      </section>
    </aside>

  </div>

  <footer class="foot">
    <span>Margin bridge · base → upside → constrained.</span>
    <span id="prov"></span>
    <span id="stamp"></span>
  </footer>
</div>

<div class="tip" id="tip" role="status" aria-live="polite"></div>

<div class="modal-scrim" id="scrim" role="dialog" aria-modal="true" aria-labelledby="modaltitle">
  <div class="modal" id="modal">
    <button class="modal__close" id="modalclose" type="button" aria-label="Close">✕</button>
    <div id="modalbody"></div>
  </div>
</div>

<script>const DATA = __DATA_JSON__;</script>
<script>
/*
 * engine-port.js — a faithful JS port of the S&OP engine's arithmetic.
 *
 * Mirrors src/sop_integrated_planning/{demand,capacity,constrain,finance}.py
 * so that a lever drag can recompute a scenario entirely client-side
 * (SCOPE §2 row 7) with NO Python round-trip. The one thing this port is
 * for is reproducing the Python engine byte-for-byte for the identity
 * lever set: the golden-fixture test (tests/test_js_port.py) asserts
 * 0-diff against mockups/data.js, which is generated by the real engine.
 *
 * This file is dual-use: it loads in the browser (the dashboard's app
 * script sets window.LEVER_ENGINE from the module body) AND under Node
 * (module.exports) for the golden-fixture harness. It must therefore
 * reference no DOM, no window/document at load time.
 *
 * The two deliberate decisions this port encodes, with reasons:
 *  1. Rationing sorts by RAW unit_margin, not by contribution-per-
 *     bottleneck-hour. SCOPE §8b #1 says the engine SHOULD sort by the
 *     latter, but the shipped engine and the golden fixture encode the
 *     former. The port must match the fixture, or 0-diff is unreachable.
 *     The §8b correction is a separate engine change with its own test.
 *  2. Rounding is Python's banker's rounding (ties-to-even on the decimal
 *     expansion), NOT JS Math.round (ties-away on the binary float).
 *     pyRound() below reproduces Python exactly; without it the golden
 *     gate fails on real data (e.g. 3008.125, 2007.7849999999999).
 *
 * The engine input is D (the embedded const DATA) mutated by lever
 * overrides — levers alter D.families / D.resources (canonical inputs),
 * never D.scenarios (precomputed outputs). "custom" is a scenario key on
 * the JS side only; Python never emits it.
 */
(function (root, factory) {
  var mod = factory();
  if (typeof module !== "undefined" && module.exports) {
    module.exports = mod;                 // Node: golden-fixture harness
  }
  if (root) {
    root.LEVER_ENGINE = mod;              // Browser: dashboard app script
  }
})(typeof self !== "undefined" ? self : typeof globalThis !== "undefined" ? globalThis : null, function () {
  "use strict";

  var MONTHS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12];
  // custom defaults to CONSTRAINED semantics: per-family upside uplift IS
  // applied (the lever scenario starts from the same demand as the shipped
  // constrained plan), capacity is held at installed hours, and rationing is
  // by unit margin unless the user changes the rule. It is NOT the base
  // plan. This keeps "custom with no levers moved" == the constrained
  // scenario, which is what the dashboard shows on first render.
  var UPLIFT_SCENARIOS = { upside: true, constrained: true, custom: true };
  var EPS = 1e-9;

  /* ---- Python-compatible banker's rounding --------------------------------
     Python round(x, dp) rounds ties to even on the DECIMAL expansion; JS
     Math.round(x*10^dp)/10^dp rounds ties away on the BINARY float. These
     diverge on real data. Strategy: get the number's full decimal
     representation via toFixed(20), walk the significant digits, decide the
     tie, then round-half-to-even. */
  function pyRound(x, dp) {
    if (dp === undefined) dp = 0;
    if (x === Infinity || x === -Infinity) return x;
    if (x !== x) return x;                       // NaN
    var neg = x < 0 || (x === 0 && 1 / x < 0);
    var s = Math.abs(x).toFixed(20);
    // integer part and fraction digits
    var dot = s.indexOf(".");
    var ip = s.slice(0, dot);
    var frac = s.slice(dot + 1);
    // strip trailing zeros
    var f = frac.replace(/0+$/, "");
    // we need digit at position dp+1 (1-based) to decide, and all after it
    if (dp < 0) {
      // rounding to an integer multiple of 10^(-dp)
      dp = 0;
    }
    var digits = (ip + f);                        // significant decimal digits
    var intVal = parseInt(ip, 10);
    if (digits.length <= dp) {
      // not enough fractional digits to matter; value is already exact
      return neg ? -Number(ip + "." + f) : Number(ip + "." + f);
    }
    var factor = Math.pow(10, dp);
    // Treat the value as a fixed-point number with `dp` decimals: integer
    // part stays integer, fraction contributes dp digits (zero-padded).
    var keep = ip.length + dp;                       // digits needed for the scaled value
    var scaled = (ip + f) || "0";
    // zero-pad right so slice(0, keep) always has `keep` digits
    while (scaled.length < keep) scaled += "0";
    var head = scaled.slice(0, keep);                // integer part of scaled value
    var tail = scaled.slice(keep);                   // the rest decides rounding
    var headVal = parseInt(head || "0", 10);
    var tailVal = tail.length ? parseInt(tail, 10) : 0;
    var firstTail = tail.length ? parseInt(tail[0], 10) : 0;
    var roundUp = false;
    if (tailVal > 0) {
      if (firstTail > 5) roundUp = true;
      else if (firstTail === 5) {
        var rest = tail.slice(1);
        var restVal = rest.length ? parseInt(rest, 10) : 0;
        if (restVal > 0) roundUp = true;
        else roundUp = (headVal % 2 === 1);          // exact tie: round to even
      }
      if (roundUp) headVal += 1;
    }
    var out = headVal / factor;
    return neg ? -out : out;
  }

  /* ---- demand.py ---------------------------------------------------------*/
  function demandUnits(family, month, tag) {
    var base = family.base_monthly_demand[month - 1];
    if (UPLIFT_SCENARIOS[tag]) {
      return pyRound(base * (1 + family.upside_uplift_pct), 2);
    }
    return base;
  }

  /* ---- capacity.py compute_loads ------------------------------------------*/
  function computeLoads(families, resources, tag, demandByFm) {
    var loads = [];
    resources.forEach(function (resource) {
      MONTHS.forEach(function (month) {
        var loadHours = 0;
        families.forEach(function (family) {
          var hpu = (family.resource_hours_per_unit[resource.id] || 0);
          if (hpu <= 0) return;
          var demand = demandByFm[family.id + "|" + month] || 0;
          loadHours += demand * hpu;
        });
        loadHours = pyRound(loadHours, 2);
        var utilization = resource.monthly_available_hours
          ? (loadHours / resource.monthly_available_hours * 100.0)
          : 0.0;
        loads.push({
          scenario: tag,
          resource_id: resource.id,
          month: month,
          load_hours: loadHours,
          available_hours: resource.monthly_available_hours,
          utilization_pct: pyRound(utilization, 2),
          is_bottleneck: utilization > 100.0,
        });
      });
    });
    return loads;
  }

  function loadHoursByResourceMonth(loads) {
    var map = {};
    loads.forEach(function (ld) {
      map[ld.resource_id + "|" + ld.month] = ld.load_hours;
    });
    return map;
  }

  function loadLookup(loads) {
    var map = {};
    loads.forEach(function (ld) {
      map[ld.resource_id + "|" + ld.month] = ld;
    });
    return map;
  }

  /* ---- constrain.py effective_capacity_hours ------------------------------*/
  function effectiveCapacity(tag, resource, loadHours) {
    if (tag === "upside") return Math.max(resource.monthly_available_hours, loadHours);
    return resource.monthly_available_hours;
  }

  /* ---- constrain.py _allowed_units_this_month ------------------------------
     rationRule: "throughput-per-constraint" (default, matches Python) |
                 "fair-share" (new) | "strategic-priority" (new).            */
  function allowedUnitsThisMonth(month, families, resources, demandByFm, loadByRm, tag, rationRule) {
    var allowed = {};
    resources.forEach(function (resource) {
      var users = families.filter(function (f) {
        return (f.resource_hours_per_unit[resource.id] || 0) > 0;
      });
      if (!users.length) return;
      var loadHours = loadByRm[resource.id + "|" + month] || 0;
      var capacityHours = effectiveCapacity(tag, resource, loadHours);

      if (loadHours <= capacityHours + EPS) {
        users.forEach(function (family) {
          allowed[family.id + "|" + resource.id] = demandByFm[family.id + "|" + month] || 0;
        });
        return;
      }

      // ration: order by the chosen rule. Fair-share allocates proportionally
      // to each user's demand (an equal service ratio); the others are greedy
      // priority fills.
      if (rationRule === "fair-share") {
        var totalAsk = 0;
        users.forEach(function (u) {
          totalAsk += (demandByFm[u.id + "|" + month] || 0) * u.resource_hours_per_unit[resource.id];
        });
        var ratio = totalAsk > 0 ? capacityHours / totalAsk : 0;
        users.forEach(function (u) {
          var want = (demandByFm[u.id + "|" + month] || 0) * u.resource_hours_per_unit[resource.id];
          var granted = Math.min(want, want * ratio);
          allowed[u.id + "|" + resource.id] = u.resource_hours_per_unit[resource.id] > 0
            ? granted / u.resource_hours_per_unit[resource.id] : (demandByFm[u.id + "|" + month] || 0);
        });
        return;
      }

      var ordered = users.slice();
      if (rationRule === "strategic-priority") {
        // honest "priority" = unit-margin tiers (documented); higher margin first
        ordered.sort(function (a, b) { return b.unit_margin - a.unit_margin; });
      } else {
        // throughput-per-constraint — descending unit_margin (matches Python)
        ordered.sort(function (a, b) { return b.unit_margin - a.unit_margin; });
      }

      var remaining = capacityHours;
      ordered.forEach(function (family) {
        var hpu = family.resource_hours_per_unit[resource.id];
        var demand = demandByFm[family.id + "|" + month] || 0;
        var wanted = demand * hpu;
        var granted = Math.max(0, Math.min(wanted, remaining));
        allowed[family.id + "|" + resource.id] = hpu > 0 ? granted / hpu : demand;
        remaining = Math.max(0, remaining - granted);
      });
    });
    return allowed;
  }

  /* ---- constrain.py build_supply_plan -------------------------------------*/
  function buildSupplyPlan(families, resources, tag, rationRule) {
    var demandByFm = {};
    families.forEach(function (f) {
      MONTHS.forEach(function (m) {
        demandByFm[f.id + "|" + m] = demandUnits(f, m, tag);
      });
    });
    var loads = computeLoads(families, resources, tag, demandByFm);
    var loadByRm = loadHoursByResourceMonth(loads);

    var opening = {};
    families.forEach(function (f) { opening[f.id] = f.opening_inventory_units; });
    var lines = [];

    MONTHS.forEach(function (month) {
      var allowed = allowedUnitsThisMonth(month, families, resources, demandByFm, loadByRm, tag, rationRule);
      families.forEach(function (family) {
        var demand = demandByFm[family.id + "|" + month] || 0;
        var usedResources = Object.keys(family.resource_hours_per_unit).filter(function (rid) {
          return family.resource_hours_per_unit[rid] > 0;
        });
        var produced;
        if (usedResources.length) {
          produced = Math.min.apply(null, usedResources.map(function (rid) {
            return allowed[family.id + "|" + rid];
          }));
        } else {
          produced = demand;
        }
        // no build-ahead: never produce more than the month's own demand
        produced = Math.max(0, Math.min(produced, demand));

        var openingUnits = opening[family.id];
        var shipped = Math.min(openingUnits + produced, demand);
        var unmet = Math.max(0, demand - shipped);
        var ending = Math.max(0, openingUnits + produced - shipped);
        var fillRate = demand > 0 ? shipped / demand : 1.0;

        lines.push({
          scenario: tag,
          family_id: family.id,
          month: month,
          demand_units: pyRound(demand, 2),
          produced_units: pyRound(produced, 2),
          opening_inventory_units: pyRound(openingUnits, 2),
          shipped_units: pyRound(shipped, 2),
          unmet_units: pyRound(unmet, 2),
          ending_inventory_units: pyRound(ending, 2),
          fill_rate: pyRound(fillRate, 4),
        });
        opening[family.id] = ending;   // RAW, unrounded — matches constrain.py:144
      });
    });

    return { lines: lines, loads: loads };
  }

  /* ---- finance.py ----------------------------------------------------------*/
  function buildFinance(supplyLines, families) {
    var byId = {};
    families.forEach(function (f) { byId[f.id] = f; });
    return supplyLines.map(function (sl) {
      var family = byId[sl.family_id];
      return {
        scenario: sl.scenario,
        family_id: sl.family_id,
        month: sl.month,
        revenue: pyRound(sl.shipped_units * family.unit_price, 2),
        gross_margin: pyRound(sl.shipped_units * family.unit_margin, 2),
        lost_revenue: pyRound(sl.unmet_units * family.unit_price, 2),
        lost_margin: pyRound(sl.unmet_units * family.unit_margin, 2),
        inventory_value: pyRound(sl.ending_inventory_units * family.unit_variable_cost, 2),
      };
    });
  }

  function summarize(tag, supplyLines, financeLines) {
    var totalDemand = 0, totalShipped = 0;
    supplyLines.forEach(function (sl) {
      totalDemand += sl.demand_units;
      totalShipped += sl.shipped_units;
    });
    var fill = totalDemand > 0 ? totalShipped / totalDemand : 1.0;
    // ending inventory value = December only (point-in-time balance)
    var decValue = 0;
    financeLines.forEach(function (fl) {
      if (fl.month === 12) decValue += fl.inventory_value;
    });
    var totalRev = 0, totalGM = 0, totalLostRev = 0, totalLostM = 0;
    financeLines.forEach(function (fl) {
      totalRev += fl.revenue;
      totalGM += fl.gross_margin;
      totalLostRev += fl.lost_revenue;
      totalLostM += fl.lost_margin;
    });
    return {
      scenario: tag,
      total_revenue: pyRound(totalRev, 2),
      total_gross_margin: pyRound(totalGM, 2),
      total_lost_revenue: pyRound(totalLostRev, 2),
      total_lost_margin: pyRound(totalLostM, 2),
      ending_inventory_value: pyRound(decValue, 2),
      fill_rate: pyRound(fill, 4),
    };
  }

  function grossMarginByFamily(financeLines) {
    var m = {};
    financeLines.forEach(function (fl) {
      m[fl.family_id] = (m[fl.family_id] || 0) + fl.gross_margin;
    });
    var out = {};
    Object.keys(m).forEach(function (k) { out[k] = pyRound(m[k], 2); });
    return out;
  }

  function lostMarginByFamily(financeLines) {
    var m = {};
    financeLines.forEach(function (fl) {
      m[fl.family_id] = (m[fl.family_id] || 0) + fl.lost_margin;
    });
    var out = {};
    Object.keys(m).forEach(function (k) { out[k] = pyRound(m[k], 2); });
    return out;
  }

  /* ---- dashboard.py _scenario_monthly_totals + finance merge ----------------*/
  function buildMonthly(supplyLines, financeLines) {
    var totals = {};
    MONTHS.forEach(function (m) { totals[m] = { demand: 0, produced: 0, shipped: 0, unmet: 0 }; });
    supplyLines.forEach(function (sl) {
      var t = totals[sl.month];
      t.demand += sl.demand_units;
      t.produced += sl.produced_units;
      t.shipped += sl.shipped_units;
      t.unmet += sl.unmet_units;
    });
    var byMonthFin = {};
    financeLines.forEach(function (fl) {
      var b = byMonthFin[fl.month] = byMonthFin[fl.month] || { revenue: 0, gross_margin: 0, lost_revenue: 0, lost_margin: 0 };
      b.revenue += fl.revenue;
      b.gross_margin += fl.gross_margin;
      b.lost_revenue += fl.lost_revenue;
      b.lost_margin += fl.lost_margin;
    });
    return MONTHS.map(function (m) {
      var f = byMonthFin[m] || { revenue: 0, gross_margin: 0, lost_revenue: 0, lost_margin: 0 };
      return {
        month: m,
        name: MONTH_NAMES[m - 1],
        demand: pyRound(totals[m].demand, 1),
        produced: pyRound(totals[m].produced, 1),
        shipped: pyRound(totals[m].shipped, 1),
        unmet: pyRound(totals[m].unmet, 1),
        revenue: pyRound(f.revenue, 2),
        gross_margin: pyRound(f.gross_margin, 2),
        lost_revenue: pyRound(f.lost_revenue, 2),
        lost_margin: pyRound(f.lost_margin, 2),
      };
    });
  }

  var MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                     "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

  /* ---- dashboard.py _family_reconciliation_rows -----------------------------*/
  function buildReconciliation(families, supplyLines, financeLines) {
    var gmByFam = grossMarginByFamily(financeLines);
    var lmByFam = lostMarginByFamily(financeLines);
    return families.map(function (family) {
      var famSupply = supplyLines.filter(function (s) { return s.family_id === family.id; });
      var famFinance = financeLines.filter(function (f) { return f.family_id === family.id; });
      var totalDemand = 0, totalShipped = 0, totalUnmet = 0;
      famSupply.forEach(function (s) {
        totalDemand += s.demand_units;
        totalShipped += s.shipped_units;
        totalUnmet += s.unmet_units;
      });
      var december = null;
      famFinance.forEach(function (f) { if (f.month === 12) december = f; });
      var fillRate = totalDemand > 0 ? (totalShipped / totalDemand * 100.0) : 100.0;
      return {
        family_id: family.id,
        family_name: family.name,
        unit_margin: family.unit_margin,
        demand_units: pyRound(totalDemand, 1),
        shipped_units: pyRound(totalShipped, 1),
        unmet_units: pyRound(totalUnmet, 1),
        fill_rate_pct: pyRound(fillRate, 1),
        revenue: pyRound(famFinance.reduce(function (a, f) { return a + f.revenue; }, 0), 2),
        gross_margin: gmByFam[family.id] || 0.0,
        lost_margin: lmByFam[family.id] || 0.0,
        ending_inventory_value: december ? december.inventory_value : 0.0,
      };
    });
  }

  /* ---- dashboard.py _provenance ---------------------------------------------*/
  function buildProvenance(tag, families, resources, demandByFm, loadByRm, loads, supplyLines, financeLines) {
    var resById = {};
    resources.forEach(function (r) { resById[r.id] = r; });
    var loadLk = loadLookup(loads);
    var supplyLk = {};
    supplyLines.forEach(function (sl) { supplyLk[sl.family_id + "|" + sl.month] = sl; });
    var financeLk = {};
    financeLines.forEach(function (fl) { financeLk[fl.family_id + "|" + fl.month] = fl; });
    var allowedByMonth = {};
    MONTHS.forEach(function (m) {
      allowedByMonth[m] = allowedUnitsThisMonth(m, families, resources, demandByFm, loadByRm, tag, "throughput-per-constraint");
    });

    var out = {};
    families.forEach(function (family) {
      var resourceIds = Object.keys(family.resource_hours_per_unit).filter(function (rid) {
        return family.resource_hours_per_unit[rid] > 0;
      });
      var monthsOut = {};
      MONTHS.forEach(function (month) {
        var demandUnitsV = demandByFm[family.id + "|" + month] || 0;
        var upliftApplied = UPLIFT_SCENARIOS[tag];
        var allowed = allowedByMonth[month];

        var capacityRows = [], rationingRows = [];
        resourceIds.forEach(function (rid) {
          var resource = resById[rid];
          var ld = loadLk[rid + "|" + month];
          var hpu = family.resource_hours_per_unit[rid];
          capacityRows.push({
            resource_id: rid,
            load_hours: ld.load_hours,
            available_hours: ld.available_hours,
            utilization_pct: ld.utilization_pct,
            is_bottleneck: ld.is_bottleneck,
            hours_per_unit: hpu,
          });

          var effHours = effectiveCapacity(tag, resource, ld.load_hours);
          var constrained = ld.load_hours > effHours + EPS;
          var users = families.filter(function (f) { return (f.resource_hours_per_unit[rid] || 0) > 0; })
            .sort(function (a, b) { return b.unit_margin - a.unit_margin; });
          var cumulative = 0;
          var row = null;
          users.forEach(function (u, i) {
            var uAllowedUnits = allowed[u.id + "|" + rid];
            var uGrantedHours = uAllowedUnits * u.resource_hours_per_unit[rid];
            if (u.id === family.id) {
              var wanted = (demandByFm[u.id + "|" + month] || 0) * u.resource_hours_per_unit[rid];
              var remainingBefore = Math.max(0, effHours - cumulative);
              var remainingAfter = Math.max(0, remainingBefore - uGrantedHours);
              row = {
                resource_id: rid,
                constrained: constrained,
                rank: i + 1,
                n_users: users.length,
                unit_margin: pyRound(u.unit_margin, 2),
                wanted_hours: pyRound(wanted, 2),
                remaining_before_hours: pyRound(remainingBefore, 2),
                granted_hours: pyRound(uGrantedHours, 2),
                remaining_after_hours: pyRound(remainingAfter, 2),
                allowed_units: pyRound(uAllowedUnits, 2),
              };
            }
            cumulative += uGrantedHours;
          });
          rationingRows.push(row);
        });

        var sl = supplyLk[family.id + "|" + month];
        var fl = financeLk[family.id + "|" + month];
        monthsOut[String(month)] = {
          demand: {
            base_units: family.base_monthly_demand[month - 1],
            uplift_pct: upliftApplied ? family.upside_uplift_pct : 0.0,
            uplift_applied: upliftApplied,
            demand_units: pyRound(demandUnitsV, 2),
          },
          capacity: capacityRows,
          rationing: rationingRows,
          supply: sl,
          financials: {
            scenario: fl.scenario,
            family_id: fl.family_id,
            month: fl.month,
            revenue: fl.revenue,
            gross_margin: fl.gross_margin,
            lost_revenue: fl.lost_revenue,
            lost_margin: fl.lost_margin,
            inventory_value: fl.inventory_value,
            unit_price: family.unit_price,
            unit_variable_cost: family.unit_variable_cost,
            unit_margin: family.unit_margin,
          },
        };
      });
      out[family.id] = monthsOut;
    });
    return out;
  }

  /* ---- applyLevers: mutate D.families / D.resources -------------------------*/
  function applyLevers(D, levers) {
    levers = levers || {};
    var families = D.families.map(function (f) {
      var fam = Object.assign({}, f, { resource_hours_per_unit: Object.assign({}, f.resource_hours_per_unit) });
      var base = fam.base_monthly_demand.slice();
      // seasonality shift (± months): circular rotate of base_monthly_demand
      var shift = levers.seasonShift || 0;
      if (shift !== 0) {
        var n = ((shift % 12) + 12) % 12;
        base = base.slice(12 - n).concat(base.slice(0, 12 - n));
      }
      var volMult = (levers.volMult || 0) / 100;
      fam.base_monthly_demand = base.map(function (v) { return v * (1 + volMult); });
      if (levers.familyUplift && levers.familyUplift[f.id] !== undefined) {
        fam.upside_uplift_pct = levers.familyUplift[f.id] / 100;
      }
      if (levers.priceDeltaPct && levers.priceDeltaPct[f.id] !== undefined) {
        fam.unit_price = fam.unit_price * (1 + levers.priceDeltaPct[f.id] / 100);
      }
      if (levers.vcDeltaPct && levers.vcDeltaPct[f.id] !== undefined) {
        fam.unit_variable_cost = fam.unit_variable_cost * (1 + levers.vcDeltaPct[f.id] / 100);
      }
      // unit_margin must be recomputed (not stale) — it's the rationing sort key
      fam.unit_margin = pyRound(fam.unit_price - fam.unit_variable_cost, 4);
      if (levers.openingDeltaPct && levers.openingDeltaPct[f.id] !== undefined) {
        fam.opening_inventory_units = fam.opening_inventory_units * (1 + levers.openingDeltaPct[f.id] / 100);
      }
      return fam;
    });
    var resources = D.resources.map(function (r) {
      var res = Object.assign({}, r);
      if (levers.hours && levers.hours[r.id] !== undefined) {
        res.monthly_available_hours = levers.hours[r.id];
      }
      return res;
    });
    return { families: families, resources: resources };
  }

  /* ---- recomputeScenario: the full pipeline --------------------------------*/
  function recomputeScenario(D, levers, tag) {
    tag = tag || "custom";
    var mutated = applyLevers(D, levers);
    var families = mutated.families, resources = mutated.resources;
    var rationRule = (levers && levers.rationRule) || "throughput-per-constraint";

    var demandByFm = {};
    families.forEach(function (f) {
      MONTHS.forEach(function (m) {
        demandByFm[f.id + "|" + m] = demandUnits(f, m, tag);
      });
    });
    var loads = computeLoads(families, resources, tag, demandByFm);
    var loadByRm = loadHoursByResourceMonth(loads);
    var plan = buildSupplyPlan(families, resources, tag, rationRule);
    var financeLines = buildFinance(plan.lines, families);
    var summary = summarize(tag, plan.lines, financeLines);
    var monthly = buildMonthly(plan.lines, financeLines);
    var utilization = {};
    resources.forEach(function (r) {
      utilization[r.id] = loads.filter(function (ld) { return ld.resource_id === r.id; })
        .map(function (ld) {
          return { month: ld.month, load_hours: ld.load_hours, available_hours: ld.available_hours, utilization_pct: ld.utilization_pct };
        });
    });
    var reconciliation = buildReconciliation(families, plan.lines, financeLines);
    var provenance = buildProvenance(tag, families, resources, demandByFm, loadByRm, loads, plan.lines, financeLines);

    return {
      scenario: { summary: summary, monthly: monthly, utilization: utilization, reconciliation: reconciliation },
      provenance: provenance,
    };
  }

  return {
    pyRound: pyRound,
    applyLevers: applyLevers,
    demandUnits: demandUnits,
    computeLoads: computeLoads,
    effectiveCapacity: effectiveCapacity,
    allowedUnitsThisMonth: allowedUnitsThisMonth,
    buildSupplyPlan: buildSupplyPlan,
    buildFinance: buildFinance,
    summarize: summarize,
    buildMonthly: buildMonthly,
    buildReconciliation: buildReconciliation,
    buildProvenance: buildProvenance,
    recomputeScenario: recomputeScenario,
  };
});

(function () {
  "use strict";
  // DATA is defined by the build template's separate <script> block
  // (const DATA = __DATA_JSON__;). It is global-scoped across classic
  // scripts, so referencing it here by name works; window.SOP_DATA does
  // not exist in the built dashboard.
  var D = typeof DATA !== "undefined" ? DATA : window.SOP_DATA;
  var SC = ["base", "upside", "constrained"];
  var SC_LABEL = { base: "Base", upside: "Upside", constrained: "Constrained", custom: "Custom (levers)" };
  var focus = "constrained";
  var MONTHS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12];

  /* ---- formatting (m1/m2/m3/m4/m5 — unified) ----------------------------- */
  function money(v) {
    var sign = v < 0 ? "-" : "";
    var a = Math.abs(v);
    if (a >= 1e6) return sign + "$" + (a / 1e6).toFixed(2) + "M";
    if (a >= 1e3) return sign + "$" + (a / 1e3).toFixed(0) + "k";
    return sign + "$" + a.toFixed(0);
  }
  function money2(v) { return "$" + v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }); }
  function units(v) { return Math.round(v).toLocaleString("en-US"); }
  function units2(v) { return v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }); }
  function pct(v, dp) { return v.toFixed(dp === undefined ? 1 : dp) + "%"; }
  function hrs(v) { return v.toLocaleString("en-US", { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + " h"; }
  function signed(v, dp) { return (v >= 0 ? "+" : "−") + Math.abs(v).toFixed(dp === undefined ? 1 : dp); }

  function deltaEl(delta, goodIsUp, unit, dp) {
    var s = document.createElement("span");
    var flat = Math.abs(delta) < 0.005;
    var good = goodIsUp === false ? delta < 0 : delta > 0;
    s.className = "delta " + (flat ? "delta--flat" : good ? "delta--good" : "delta--bad");
    s.textContent = (flat ? "▬ " : delta > 0 ? "▲ " : "▼ ") + signed(delta, dp) + (unit ? " " + unit : "%");
    return s;
  }

  // SVG namespace URI. Built without a literal "http:" scheme so the
  // rendered file stays greppable-clean for network references (the
  // dashboard is zero-CDN; this is a fixed URN the SVG spec requires,
  // never a fetch).
  var SVG_NS = "http:" + "//www.w3.org/2000/svg";
  function svgEl(tag, attrs) {
    var e = document.createElementNS(SVG_NS, tag);
    for (var k in attrs) if (attrs[k] !== undefined && attrs[k] !== null) e.setAttribute(k, attrs[k]);
    return e;
  }

  // Scenario identity = fill pattern, never hue (SCOPE §8b).
  function paintScenario(el, sid) {
    if (sid === "constrained") el.setAttribute("fill", "url(#hatch)");
    else if (sid === "custom") el.setAttribute("fill", "var(--sop-color-brand)");
    else if (sid === "upside") el.setAttribute("fill", "var(--sop-color-ink-soft)");
    else {
      el.setAttribute("fill", "var(--sop-color-chart-actual)");
      el.setAttribute("fill-opacity", "0.85");
    }
  }

  // IBCS notation for time-series rows (m1): actual = solid ink, plan =
  // outline, constrained = hatched (dashed stroke stands in for a stroke).
  function paint(el, style, sid) {
    if (style === "plan") {
      el.setAttribute("fill", "none");
      el.setAttribute("stroke", "var(--sop-color-ink-soft)");
      el.setAttribute("stroke-width", "1");
    } else if (sid === "constrained") {
      el.setAttribute("fill", "url(#hatch)");
    } else if (sid === "custom") {
      el.setAttribute("fill", "var(--sop-color-brand)");
      el.setAttribute("fill-opacity", "0.85");
    } else if (sid === "upside") {
      el.setAttribute("fill", "var(--sop-color-ink-soft)");
    } else {
      el.setAttribute("fill", "var(--sop-color-chart-actual)");
      el.setAttribute("fill-opacity", "0.85");
    }
  }

  /* ---- tooltip (m1's richer variant — head + rows + foot) ---------------- */
  var tip = document.getElementById("tip");
  function showTip(evt, head, rows, foot) {
    tip.innerHTML = "";
    var h = document.createElement("div"); h.className = "tip__head"; h.textContent = head; tip.appendChild(h);
    (rows || []).forEach(function (r) {
      var d = document.createElement("div"); d.className = "tip__row";
      var a = document.createElement("span"); a.textContent = r[0];
      var b = document.createElement("b"); b.textContent = r[1];
      d.appendChild(a); d.appendChild(b); tip.appendChild(d);
    });
    if (foot) { var f = document.createElement("div"); f.className = "tip__foot"; f.textContent = foot; tip.appendChild(f); }
    tip.dataset.show = "1";
    var x = evt.clientX + 14, y = evt.clientY + 14;
    if (x + 300 > window.innerWidth) x = evt.clientX - 300;
    if (y + 150 > window.innerHeight) y = evt.clientY - 150;
    tip.style.left = x + "px"; tip.style.top = y + "px";
  }
  function hideTip() { tip.dataset.show = "0"; }

  /* ---- derived aggregates (m2) ------------------------------------------- */
  function agg(sid) {
    var s = D.scenarios[sid], m = s.monthly;
    var unmet = m.reduce(function (a, r) { return a + r.unmet; }, 0);
    var demand = m.reduce(function (a, r) { return a + r.demand; }, 0);
    // For custom, use the scenario's own peak-utilization resource (the
    // recompute may have moved the bottleneck); else the shipped one.
    var utilKey = D.bottleneck.resource_id;
    if (sid === "custom") {
      utilKey = Object.keys(s.utilization).reduce(function (best, rid) {
        var pk = Math.max.apply(null, s.utilization[rid].map(function (x) { return x.utilization_pct; }));
        return pk > best.pk ? { rid: rid, pk: pk } : best;
      }, { rid: utilKey, pk: 0 }).rid;
    }
    var util = s.utilization[utilKey];
    return {
      revenue: s.summary.total_revenue,
      margin: s.summary.total_gross_margin,
      lost_margin: s.summary.total_lost_margin,
      inventory: s.summary.ending_inventory_value,
      fill: s.summary.fill_rate * 100,
      unmet: unmet,
      demand: demand,
      peak_util: Math.max.apply(null, util.map(function (r) { return r.utilization_pct; })),
      months_over: util.filter(function (r) { return r.utilization_pct > 100; }).length
    };
  }
  var A = { base: agg("base"), constrained: agg("constrained"), upside: agg("upside") };
  // custom starts as constrained (no levers touched); becomes a real engine
  // recompute the moment any wired lever moves (applyLeversAndRecompute).
  D.scenarios.custom = D.scenarios.constrained;
  D.provenance.custom = D.provenance.constrained;
  A.custom = agg("custom");

  function resName(rid) { return D.resources.filter(function (r) { return r.id === rid; })[0].name; }
  function lineA() { return D.scenarios.constrained.utilization[D.bottleneck.resource_id]; } // 12 months
  function peakMonth() {
    return lineA().reduce(function (a, b) { return b.utilization_pct > a.utilization_pct ? b : a; });
  }

  /* =========================================================================
     SECTION 1 — TOPBAR + THEME
     ========================================================================= */
  document.getElementById("co").textContent = "S&OP Cockpit — " + D.company;
  document.getElementById("cycle").textContent = "Annual plan · 12 monthly buckets";
  var th = document.getElementById("themetoggle");
  th.addEventListener("click", function () {
    var light = document.documentElement.getAttribute("data-theme") === "light";
    document.documentElement.setAttribute("data-theme", light ? "dark" : "light");
    th.textContent = light ? "Light" : "Dark";
  });

  /* =========================================================================
     SECTION 2 — HEADLINE BAND (m4's richer headline)
     ========================================================================= */
  function buildHeadline() {
    var base = D.scenarios.base.summary, up = D.scenarios.upside.summary, con = D.scenarios.constrained.summary;
    var lift = up.total_gross_margin - base.total_gross_margin;
    var conVsBase = con.total_gross_margin - base.total_gross_margin;
    var atRisk = con.total_lost_margin;
    var pk = peakMonth();
    document.getElementById("headline").innerHTML =
      '<div class="headline__top">' +
        '<div><span class="headline__kicker">Recommended plan</span>' +
        '<p class="headline__lede">Ship <strong>Constrained</strong>: <strong>' + money(con.total_gross_margin) + '</strong> gross margin at <strong>' + pct(con.fill_rate * 100, 2) + '</strong> fill — the realistic ceiling.</p></div>' +
        '<div><span class="headline__kicker">The one constraint</span>' +
        '<p class="headline__lede">' + resName(D.bottleneck.resource_id) + ' peaks at <strong>' + pct(pk.utilization_pct, 1) + '</strong> of installed hours in ' + D.month_names[pk.month - 1] + ' — it rations Dryers and caps the plan.</p></div>' +
      '</div>' +
      '<div class="headline__trade">' +
        'Constrained banks <span class="delta delta--good">▲ ' + money(conVsBase) + '</span> over Base' +
        ' while shedding only <span class="delta delta--bad">▼ ' + money2(atRisk) + '</span> of the ' + money(lift) + ' Upside lift (Dryers, 3 months).' +
      '</div>';
  }

  /* =========================================================================
     SECTION 3 — KPI TILES (m1)
     ========================================================================= */
  function buildTiles() {
    var base = D.scenarios.base.summary,
        up = D.scenarios.upside.summary,
        con = D.scenarios[focus].summary || D.scenarios.constrained.summary;
    var isCustom = focus === "custom";
    var tiles = [
      { label: "Revenue", value: money(con.total_revenue), delta: (con.total_revenue / base.total_revenue - 1) * 100,
        basis: "vs Base " + money(base.total_revenue), why: "shipped units × unit price" },
      { label: "Gross margin", value: money(con.total_gross_margin), delta: (con.total_gross_margin / base.total_gross_margin - 1) * 100,
        basis: "vs Base " + money(base.total_gross_margin), why: "shipped units × unit margin" },
      { label: "Fill rate", value: pct(con.fill_rate * 100, 2), delta: (con.fill_rate - base.fill_rate) * 100,
        deltaUnit: "pp", deltaDp: 2,
        basis: "vs Base " + pct(base.fill_rate * 100, 2), why: "shipped ÷ demanded, full year" },
      { label: "Lost margin", value: money(con.total_lost_margin), delta: null, goodIsUp: false,
        basis: isCustom ? "your custom lever scenario" : "Base and Upside both " + money(0),
        why: "unmet units × unit margin" }
    ];
    var host = document.getElementById("tiles");
    host.innerHTML = "";
    tiles.forEach(function (t) {
      var el = document.createElement("div"); el.className = "tile";
      var lab = document.createElement("div"); lab.className = "tile__label"; lab.textContent = t.label;
      var why = document.createElement("button"); why.className = "why"; why.type = "button"; why.textContent = "why?";
      why.title = t.why + " — see the 5-step derivation below";
      lab.appendChild(why);
      var val = document.createElement("div"); val.className = "tile__value"; val.textContent = t.value;
      var foot = document.createElement("div"); foot.className = "tile__foot";
      if (t.delta !== null) foot.appendChild(deltaEl(t.delta, t.goodIsUp, t.deltaUnit, t.deltaDp));
      var b = document.createElement("span"); b.className = "basis"; b.textContent = t.basis;
      foot.appendChild(b);
      el.appendChild(lab); el.appendChild(val); el.appendChild(foot);
      host.appendChild(el);
    });
  }

  /* =========================================================================
     SECTION 4 — SMALL MULTIPLES (m1): demand vs shipped, revenue, bottleneck
     ========================================================================= */
  var ROWS = [
    {
      key: "volume", name: "Demand vs shipped", unit: "units / month", type: "bar",
      series: [
        { field: "demand", label: "Demand", style: "plan" },
        { field: "shipped", label: "Shipped", style: "actual" }
      ],
      fmt: units
    },
    {
      key: "revenue", name: "Revenue", unit: "$ / month", type: "line",
      series: [{ field: "revenue", label: "Revenue", style: "actual" }],
      fmt: money
    },
    {
      key: "util", name: resName(D.bottleneck.resource_id), unit: "% of available hours", type: "bar",
      series: [{ field: "utilization_pct", label: "Utilisation", style: "actual" }],
      fmt: function (v) { return pct(v); }, ref: 100, source: "utilization"
    }
  ];
  var SM_W = 260, SM_H = 108, SM_PL = 4, SM_PR = 4, SM_PT = 10, SM_PB = 16;

  function rowValues(row, sid) {
    if (row.source === "utilization") {
      return D.scenarios[sid].utilization[D.bottleneck.resource_id].map(function (r, i) {
        return { name: D.month_names[i], utilization_pct: r.utilization_pct,
                 load_hours: r.load_hours, available_hours: r.available_hours };
      });
    }
    return D.scenarios[sid].monthly;
  }

  function domain(row) {
    var max = 0;
    SC.forEach(function (sid) {
      rowValues(row, sid).forEach(function (d) {
        row.series.forEach(function (s) { if (d[s.field] > max) max = d[s.field]; });
      });
    });
    if (row.ref && row.ref > max) max = row.ref;
    return [0, max * 1.08];
  }

  function drawCell(row, sid, dom) {
    var data = rowValues(row, sid);
    var svg = svgEl("svg", { viewBox: "0 0 " + SM_W + " " + SM_H, role: "img" });
    var plotW = SM_W - SM_PL - SM_PR, plotH = SM_H - SM_PT - SM_PB;
    var y = function (v) { return SM_PT + plotH - (v / dom[1]) * plotH; };
    var n = data.length, step = plotW / n;

    svg.appendChild(svgEl("line", { x1: SM_PL, y1: y(0), x2: SM_W - SM_PR, y2: y(0), class: "axis-line" }));

    if (row.type === "bar") {
      var multi = row.series.length > 1;
      var bw = Math.max(3, step * 0.72);
      data.forEach(function (d, i) {
        var cx = SM_PL + step * i + step / 2;
        row.series.forEach(function (s, si) {
          var v = d[s.field]; if (v === undefined || v === null) return;
          var w = !multi ? bw : (s.style === "plan" ? bw : bw * 0.5);
          var r = svgEl("rect", { x: cx - w / 2, y: y(v), width: w, height: Math.max(0.6, y(0) - y(v)), rx: 1 });
          paint(r, s.style, sid);
          svg.appendChild(r);
        });
        if (multi && d.unmet > 0) {
          svg.appendChild(svgEl("rect", {
            x: cx - bw / 2, y: y(d.demand), width: bw,
            height: Math.max(1, y(d.shipped) - y(d.demand)),
            fill: "var(--sop-color-bad)", rx: 1
          }));
        }
      });
    } else {
      var pts = data.map(function (d, i) { return [SM_PL + step * i + step / 2, y(d[row.series[0].field])]; });
      svg.appendChild(svgEl("polyline", {
        points: pts.map(function (p) { return p[0] + "," + p[1]; }).join(" "),
        fill: "none",
        stroke: sid === "base" ? "var(--sop-color-chart-actual)" : "var(--sop-color-ink-soft)",
        "stroke-width": 2, "stroke-linejoin": "round", "stroke-linecap": "round",
        "stroke-dasharray": sid === "constrained" ? "5 3" : null
      }));
    }

    if (row.ref) {
      svg.appendChild(svgEl("line", { x1: SM_PL, y1: y(row.ref), x2: SM_W - SM_PR, y2: y(row.ref), class: "ref-line" }));
      var t = svgEl("text", { x: SM_W - SM_PR, y: y(row.ref) - 3, class: "tick-text", "text-anchor": "end" });
      t.textContent = "capacity 100%"; svg.appendChild(t);
    }

    [0, 5, n - 1].forEach(function (i) {
      var t = svgEl("text", { x: SM_PL + step * i + step / 2, y: SM_H - 4, class: "tick-text", "text-anchor": "middle" });
      t.textContent = data[i].name; svg.appendChild(t);
    });

    data.forEach(function (d, i) {
      var hit = svgEl("rect", { x: SM_PL + step * i, y: SM_PT, width: step, height: plotH, class: "mark-hit" });
      hit.addEventListener("mousemove", function (e) {
        var rows = [], foot;
        if (row.source === "utilization") {
          rows.push(["Load", d.load_hours.toLocaleString("en-US") + " h"]);
          rows.push(["Available", d.available_hours.toLocaleString("en-US") + " h"]);
          rows.push(["Utilisation", pct(d.utilization_pct)]);
          foot = "load ÷ available × 100";
        } else {
          row.series.forEach(function (s) { rows.push([s.label, row.fmt(d[s.field])]); });
          if (d.unmet !== undefined && row.key === "volume") rows.push(["Unmet", units(d.unmet)]);
          if (row.key === "revenue") foot = "shipped units × unit price";
        }
        showTip(e, SC_LABEL[sid] + " · " + d.name, rows, foot);
      });
      hit.addEventListener("mouseleave", hideTip);
      svg.appendChild(hit);
    });
    return svg;
  }

  function buildSmallMultiples() {
    var sm = document.getElementById("sm");
    sm.appendChild(Object.assign(document.createElement("div"), { className: "sm__corner" }));
    SC.forEach(function (sid) {
      var h = document.createElement("div"); h.className = "sm__colhead";
      var n = document.createElement("span"); n.className = "sm__colhead-name"; n.textContent = SC_LABEL[sid];
      var s = document.createElement("span"); s.className = "sm__colhead-sub";
      s.textContent = money(D.scenarios[sid].summary.total_gross_margin) + " GM";
      h.appendChild(n); h.appendChild(s); sm.appendChild(h);
    });
    ROWS.forEach(function (row) {
      var dom = domain(row);
      var rh = document.createElement("div"); rh.className = "sm__rowhead";
      var nm = document.createElement("div"); nm.className = "sm__rowhead-name"; nm.textContent = row.name;
      var un = document.createElement("div"); un.className = "sm__rowhead-unit"; un.textContent = row.unit;
      var sc = document.createElement("div"); sc.className = "sm__rowhead-scale";
      sc.textContent = "0 – " + row.fmt(dom[1]) + " (shared)";
      rh.appendChild(nm); rh.appendChild(un); rh.appendChild(sc);
      sm.appendChild(rh);
      SC.forEach(function (sid) {
        var c = document.createElement("div"); c.className = "sm__cell";
        c.appendChild(drawCell(row, sid, dom)); sm.appendChild(c);
      });
    });
  }

  /* =========================================================================
     SECTION 5 — SCENARIO PRESETS + STRUCTURAL COMPARISON (m2)
     ========================================================================= */
  var PRESETS = [
    { id: "S0", key: "base", name: "Base", q: "What does the consensus plan look like?" },
    { id: "S1", key: "constrained", name: "Constrained", q: "What can we actually make?" },
    { id: "S2", key: "upside", name: "Upside", q: "What if demand lands high?" },
    { id: "S3", key: "custom", name: "Custom", q: "Build it with the levers below.",
      tag: "levers" },
    { id: "S4", key: null, name: "Invest", q: "Is relieving the bottleneck worth it?",
      tag: "not in engine", disabled: true }
  ];
  function buildPresets() {
    var presetHost = document.getElementById("presets");
    PRESETS.forEach(function (p) {
      var b = document.createElement("button");
      b.className = "preset"; b.type = "button";
      b.setAttribute("aria-pressed", String(p.key === focus));
      if (p.disabled) b.disabled = true;
      var id = document.createElement("div"); id.className = "preset__id";
      id.appendChild(document.createTextNode(p.id));
      if (p.tag) { var t = document.createElement("span"); t.className = "tag"; t.textContent = p.tag; id.appendChild(t); }
      var nm = document.createElement("div"); nm.className = "preset__name"; nm.textContent = p.name;
      var q = document.createElement("p"); q.className = "preset__q"; q.textContent = p.q;
      b.appendChild(id); b.appendChild(nm); b.appendChild(q);
      if (!p.disabled) b.addEventListener("click", function () {
        if (p.key === "custom") {
          // Custom recomputes from current levers; falls back to constrained
          // if no lever is dirty.
          applyLeversAndRecompute();
        } else {
          focus = p.key; renderComparison();
        }
        Array.prototype.forEach.call(presetHost.children, function (c, i) {
          c.setAttribute("aria-pressed", String(PRESETS[i].key === focus));
        });
      });
      presetHost.appendChild(b);
    });
  }

  var METRICS = [
    { key: "revenue", name: "Revenue", unit: "$ full year", fmt: money, goodIsUp: true,
      why: "shipped units × unit price, summed over 12 months" },
    { key: "margin", name: "Gross margin", unit: "$ full year", fmt: money, goodIsUp: true,
      why: "shipped units × unit margin" },
    { key: "lost_margin", name: "Lost margin", unit: "$ full year", fmt: money, goodIsUp: false,
      why: "unmet units × unit margin" },
    { key: "unmet", name: "Unmet demand", unit: "units full year", fmt: units, goodIsUp: false,
      why: "demand − shipped, summed over 12 months" },
    { key: "inventory", name: "Closing inventory", unit: "$ at variable cost", fmt: money, goodIsUp: false,
      why: "December closing units × unit variable cost" },
    { key: "fill", name: "Fill rate", unit: "% of demand served", fmt: function (v) { return pct(v, 2); },
      goodIsUp: true, deltaUnit: "pp", why: "shipped ÷ demanded" }
  ];
  var BW = 460, BH = 70, NOTE_BH = 92, GUTTER = 74, BPAD_R = 74, ROWH = 18, GAP = 4;

  function drawLevels(metric) {
    var vals = SC.map(function (s) { return A[s][metric.key]; });
    var max = Math.max.apply(null, vals);
    var min = Math.min.apply(null, vals);
    var lo = metric.key === "fill" ? Math.floor(min - 0.5) : 0;
    var hasNote = lo !== 0;
    var chartH = hasNote ? NOTE_BH : BH;
    var hi = max * 1.02 || 1;
    var plotW = BW - GUTTER - BPAD_R;
    var x = function (v) { return GUTTER + ((v - lo) / (hi - lo)) * plotW; };
    var svg = svgEl("svg", { viewBox: "0 0 " + BW + " " + chartH, role: "img" });
    SC.forEach(function (sid, i) {
      var y = i * (ROWH + GAP) + 2, v = A[sid][metric.key];
      var lab = svgEl("text", { x: GUTTER - 8, y: y + ROWH / 2 + 3.5, class: "bar-label", "text-anchor": "end" });
      lab.textContent = SC_LABEL[sid]; svg.appendChild(lab);
      var w = Math.max(0, x(v) - GUTTER);
      if (w > 0.5) {
        var r = svgEl("rect", { x: GUTTER, y: y, width: w, height: ROWH, rx: 1 });
        paintScenario(r, sid); svg.appendChild(r);
      }
      var val = svgEl("text", { x: GUTTER + w + 6, y: y + ROWH / 2 + 3.5, class: "bar-value" });
      val.textContent = metric.fmt(v); svg.appendChild(val);
      var hit = svgEl("rect", { x: 0, y: y, width: BW, height: ROWH, class: "mark-hit" });
      hit.addEventListener("mousemove", function (e) {
        var d = v - A.base[metric.key];
        showTip(e, SC_LABEL[sid] + " · " + metric.name,
          [[metric.name, metric.fmt(v)],
           ["vs Base", (d >= 0 ? "+" : "−") + metric.fmt(Math.abs(d)) + (metric.deltaUnit ? " " + metric.deltaUnit : "")]],
          metric.why);
      });
      hit.addEventListener("mouseleave", hideTip); svg.appendChild(hit);
    });
    svg.appendChild(svgEl("line", { x1: GUTTER, y1: 0, x2: GUTTER, y2: BH - 10, class: "axis-line" }));
    if (hasNote) {
      var z = svgEl("text", { x: GUTTER, y: chartH - 4, class: "tick-text" });
      z.textContent = "axis starts at " + metric.fmt(lo) + ", not zero"; svg.appendChild(z);
    }
    return svg;
  }

  function drawVariance(metric) {
    var deltas = SC.map(function (s) { return A[s][metric.key] - A.base[metric.key]; });
    var span = Math.max.apply(null, deltas.map(Math.abs)) || 1;
    var W = 230, LABEL_W = 92, mid = 26, plotW = W - LABEL_W - mid - 6;
    var x = function (d) { return mid + (d / span) * plotW; };
    var svg = svgEl("svg", { viewBox: "0 0 " + W + " " + BH, role: "img" });
    svg.appendChild(svgEl("line", { x1: mid, y1: 0, x2: mid, y2: BH - 10, class: "axis-line" }));
    SC.forEach(function (sid, i) {
      var y = i * (ROWH + GAP) + 2, d = deltas[i];
      var isBase = sid === "base";
      var flat = Math.abs(d) < 1e-9;
      var good = metric.goodIsUp ? d > 0 : d < 0;
      if (!isBase && !flat) {
        var x0 = Math.min(mid, x(d)), w = Math.abs(x(d) - mid);
        svg.appendChild(svgEl("rect", { x: x0, y: y + 4, width: Math.max(1.5, w), height: ROWH - 8, rx: 1,
          fill: good ? "var(--sop-color-good)" : "var(--sop-color-bad)" }));
      }
      var t = svgEl("text", { x: W - 2, y: y + ROWH / 2 + 3.5, class: "bar-value", "text-anchor": "end",
        fill: isBase || flat ? "var(--sop-color-text-muted)" : good ? "var(--sop-color-good)" : "var(--sop-color-bad)" });
      t.textContent = isBase ? "reference" : flat ? "▬ no change"
        : (d > 0 ? "▲ +" : "▼ −") + metric.fmt(Math.abs(d)) + (metric.deltaUnit ? " " + metric.deltaUnit : "");
      svg.appendChild(t);
    });
    return svg;
  }

  // Bullet graphs with graded bands (m2/m4 — bands are OUR thresholds).
  var BANDS = [
    { to: 85, label: "safe", fill: "rgba(52, 211, 153, 0.20)" },
    { to: 100, label: "strained", fill: "rgba(251, 191, 36, 0.22)" },
    { to: 125, label: "critical", fill: "rgba(248, 113, 113, 0.26)" }
  ];

  function bulletSvg(value, maxScale, refValue, refLabel, fmt, sid, bands) {
    var W = 400, H = 36, LABEL_W = 54, plotW = W - LABEL_W;
    var x = function (v) { return (v / maxScale) * plotW; };
    var svg = svgEl("svg", { viewBox: "0 0 " + W + " " + H, role: "img" });
    var useBands = bands || BANDS, prev = 0;
    if (useBands.length) {
      useBands.forEach(function (b) {
        svg.appendChild(svgEl("rect", { x: x(prev), y: 2, width: Math.max(0, x(Math.min(b.to, maxScale)) - x(prev)), height: 20, fill: b.fill }));
        if (prev > 0) svg.appendChild(svgEl("line", { x1: x(prev), y1: 2, x2: x(prev), y2: 22, stroke: "var(--sop-color-canvas)", "stroke-width": 1 }));
        prev = b.to;
      });
    } else {
      svg.appendChild(svgEl("rect", { x: 0, y: 2, width: plotW, height: 20, rx: 2, fill: "var(--sop-color-surface-sunken)" }));
    }
    var measure = svgEl("rect", { x: 0, y: 8.5, width: Math.max(2, x(value)), height: 7, rx: 1 });
    paintScenario(measure, sid); svg.appendChild(measure);
    svg.appendChild(svgEl("line", { x1: x(refValue), y1: 0, x2: x(refValue), y2: 24, stroke: "var(--sop-color-text-primary)", "stroke-width": 2 }));
    var rl = svgEl("text", { x: x(refValue) - 4, y: 33, class: "tick-text", "text-anchor": "end" });
    rl.textContent = refLabel; svg.appendChild(rl);
    var vl = svgEl("text", { x: W, y: 16, class: "bar-value", "text-anchor": "end" });
    vl.textContent = fmt(value); svg.appendChild(vl);
    return svg;
  }

  function renderBullets() {
    var host = document.getElementById("bullets");
    host.innerHTML = "";
    var items = D.resources.map(function (r) {
      var rows = D.scenarios[focus].utilization[r.id];
      var peak = Math.max.apply(null, rows.map(function (x) { return x.utilization_pct; }));
      var over = rows.filter(function (x) { return x.utilization_pct > 100; }).length;
      return { name: r.name, value: peak, sub: over + " of 12 months over capacity",
               fmt: function (v) { return pct(v); }, ref: 100, refLabel: "capacity", max: 125 };
    });
    items.push({
      name: "Fill rate", value: A[focus].fill, sub: "reference is full demand served, not a business target",
      fmt: function (v) { return pct(v, 2); }, ref: 100, refLabel: "all demand", max: 125, isFill: true
    });
    items.forEach(function (it) {
      var d = document.createElement("div"); d.className = "bullet";
      var h = document.createElement("div"); h.className = "bullet__head";
      var n = document.createElement("span"); n.className = "bullet__name"; n.textContent = it.name;
      var s = document.createElement("span"); s.className = "bullet__sub"; s.textContent = it.sub;
      h.appendChild(n); h.appendChild(s); d.appendChild(h);
      d.appendChild(bulletSvg(it.value, it.max, it.ref, it.refLabel, it.fmt, focus));
      host.appendChild(d);
    });
    var key = document.getElementById("bandkey");
    key.innerHTML = "";
    BANDS.forEach(function (b, i) {
      var prev = i === 0 ? 0 : BANDS[i - 1].to;
      var el = document.createElement("span"); el.className = "bandkey__item";
      el.innerHTML = '<span class="bandkey__swatch" style="background:' + b.fill +
        ';border:1px solid var(--sop-color-border-strong)"></span><span>' +
        b.label + " — " + prev + "–" + b.to + "%</span>";
      key.appendChild(el);
    });
    var f = document.createElement("span"); f.className = "bandkey__item";
    f.innerHTML = '<span style="color:var(--sop-color-text-muted)">Showing: <strong style="color:var(--sop-color-text-primary)">' +
      SC_LABEL[focus] + "</strong> — pick a preset above to switch</span>";
    key.appendChild(f);
  }

  function renderFamilies() {
    var host = document.getElementById("fam");
    host.innerHTML = "";
    ["Family", "Gross margin — shared scale", "Margin lost to rationing"].forEach(function (h, i) {
      var d = document.createElement("div");
      d.className = "cmp__colhead" + (i === 2 ? " cmp__colhead--var" : "");
      d.textContent = h; host.appendChild(d);
    });
    var recon = {};
    var scenariosIncluding = SC.slice();
    if (D.scenarios.custom) scenariosIncluding.push("custom");
    scenariosIncluding.forEach(function (s) {
      recon[s] = {};
      D.scenarios[s].reconciliation.forEach(function (r) { recon[s][r.family_id] = r; });
    });
    var fams = D.scenarios.base.reconciliation.slice().sort(function (a, b) {
      return b.gross_margin - a.gross_margin;
    });
    var maxGM = Math.max.apply(null, scenariosIncluding.map(function (s) {
      return Math.max.apply(null, D.scenarios[s].reconciliation.map(function (r) { return r.gross_margin; }));
    }));
    var maxLost = Math.max.apply(null, D.scenarios[focus].reconciliation.map(function (r) { return r.lost_margin; })) || 1;

    fams.forEach(function (f) {
      var lab = document.createElement("div"); lab.className = "cmp__metric";
      var nm = document.createElement("div"); nm.className = "cmp__metric-name"; nm.textContent = f.family_name;
      var un = document.createElement("div"); un.className = "cmp__metric-unit";
      un.textContent = "$" + f.unit_margin + " margin / unit";
      lab.appendChild(nm); lab.appendChild(un);

      var FW = 460, FH = 48, FG = 74, FR = 74, fplotW = FW - FG - FR, rowh = 12, gap = 3;
      var fsvg = svgEl("svg", { viewBox: "0 0 " + FW + " " + FH, role: "img" });
      SC.forEach(function (sid, i) {
        var r = recon[sid][f.family_id];
        var y = i * (rowh + gap) + 2;
        var fx = function (v) { return FG + (v / maxGM) * fplotW; };
        var fl = svgEl("text", { x: FG - 8, y: y + rowh / 2 + 3, class: "bar-label", "text-anchor": "end" });
        fl.textContent = SC_LABEL[sid]; fsvg.appendChild(fl);
        var fw = Math.max(0, fx(r.gross_margin) - FG);
        if (fw > 0.5) {
          var bar = svgEl("rect", { x: FG, y: y, width: fw, height: rowh, rx: 1 });
          paintScenario(bar, sid); fsvg.appendChild(bar);
        }
        var ft = svgEl("text", { x: FG + fw + 6, y: y + rowh / 2 + 3.5, class: "bar-value" });
        ft.textContent = money(r.gross_margin); fsvg.appendChild(ft);
        var hit = svgEl("rect", { x: 0, y: y, width: FW, height: rowh, class: "mark-hit" });
        hit.addEventListener("mousemove", function (e) {
          showTip(e, f.family_name + " · " + SC_LABEL[sid],
            [["Gross margin", money(r.gross_margin)],
             ["Shipped", units(r.shipped_units) + " u"],
             ["Unmet", units(r.unmet_units) + " u"],
             ["Fill rate", pct(r.fill_rate_pct, 2)]],
            "shipped units × $" + f.unit_margin + " unit margin");
        });
        hit.addEventListener("mouseleave", hideTip); fsvg.appendChild(hit);
      });
      fsvg.appendChild(svgEl("line", { x1: FG, y1: 0, x2: FG, y2: FH - 6, class: "axis-line" }));
      var bars = document.createElement("div"); bars.className = "cmp__bars"; bars.appendChild(fsvg);

      var lost = recon[focus][f.family_id].lost_margin;
      var LW = 230, LLW = 92, lmid = 26, lplotW = LW - LLW - lmid - 6;
      var lsvg = svgEl("svg", { viewBox: "0 0 " + LW + " " + FH, role: "img" });
      lsvg.appendChild(svgEl("line", { x1: lmid, y1: 0, x2: lmid, y2: FH - 6, class: "axis-line" }));
      if (lost > 0) {
        var lx = lmid + (lost / maxLost) * lplotW;
        lsvg.appendChild(svgEl("rect", { x: lmid, y: 14, width: Math.max(2, lx - lmid), height: 12, rx: 1, fill: "var(--sop-color-bad)" }));
      }
      var lt = svgEl("text", { x: LW - 2, y: 24, class: "bar-value", "text-anchor": "end",
        fill: lost > 0 ? "var(--sop-color-bad)" : "var(--sop-color-text-muted)" });
      lt.textContent = lost > 0 ? "▼ −" + money(lost) : "▬ none";
      lsvg.appendChild(lt);
      var vr = document.createElement("div"); vr.className = "cmp__var"; vr.appendChild(lsvg);

      host.appendChild(lab); host.appendChild(bars); host.appendChild(vr);
    });
    document.getElementById("famnote").textContent =
      "Gross margin by family under each scenario, plus what rationing takes off " + SC_LABEL[focus] +
      ". Sorted by Base margin — the rationing rule follows unit margin, so the order is the priority order.";
  }

  function renderComparison() {
    var cmp = document.getElementById("cmp");
    cmp.innerHTML = "";
    ["Metric", "Level — shared scale per metric", "Variance vs Base"].forEach(function (h, i) {
      var d = document.createElement("div");
      d.className = "cmp__colhead" + (i === 2 ? " cmp__colhead--var" : "");
      d.textContent = h; cmp.appendChild(d);
    });
    METRICS.forEach(function (m) {
      var lab = document.createElement("div"); lab.className = "cmp__metric";
      var nm = document.createElement("div"); nm.className = "cmp__metric-name";
      nm.appendChild(document.createTextNode(m.name));
      var w = document.createElement("button"); w.className = "why"; w.type = "button";
      w.textContent = "why?"; w.title = m.why + " — full derivation in the drill-down grid below";
      nm.appendChild(w);
      var un = document.createElement("div"); un.className = "cmp__metric-unit"; un.textContent = m.unit;
      lab.appendChild(nm); lab.appendChild(un);
      var bars = document.createElement("div"); bars.className = "cmp__bars"; bars.appendChild(drawLevels(m));
      var vr = document.createElement("div"); vr.className = "cmp__var"; vr.appendChild(drawVariance(m));
      cmp.appendChild(lab); cmp.appendChild(bars); cmp.appendChild(vr);
    });
    renderBullets();
    renderFamilies();
  }

  /* =========================================================================
     SECTION 6 — LEVERS (m3, static) + SCENARIO TABS
     ========================================================================= */
  var tabHost = document.getElementById("scenariotabs");
  SC.forEach(function (sid) {
    var b = document.createElement("button");
    b.className = "scenariotab"; b.type = "button";
    b.setAttribute("aria-pressed", String(sid === focus));
    b.textContent = SC_LABEL[sid];
    b.addEventListener("click", function () {
      focus = sid;
      Array.prototype.forEach.call(tabHost.children, function (c, i) {
        c.setAttribute("aria-pressed", String(SC[i] === focus));
      });
      renderGrid();
    });
    tabHost.appendChild(b);
  });

  var resourceCaption = D.resources.map(function (r) {
    return r.name + " " + units(r.monthly_available_hours) + " h/mo installed";
  }).join(" · ");

  // Live lever state. Each wired lever has a `key` (engine override) and a
  // `read` function that renders its current value; dragging fires
  // recomputeScenario and re-renders the focused view as the custom scenario.
  // A lever is ONLY wired when it has an expressible engine mutation
  // (SCOPE §4: "changing it must alter a named term in a formula we can
  // display, or it does not ship"). Everything else stays disabled-with-note.
  var LEVER_STATE = {};

  function readLeverValue(key) {
    return LEVER_STATE[key] !== undefined ? LEVER_STATE[key] : 0;
  }

  var TIER1 = [
    { group: "Demand", levers: [
      { key: "volMult", label: "Volume multiplier (global)", unit: "%",
        min: -50, max: 50, step: 1,
        note: "Scales every family's base monthly demand by (1 + pct/100). Alters the Demand step's base units." },
      { key: "seasonShift", label: "Seasonality shift", unit: "months",
        min: -6, max: 6, step: 1, discrete: true,
        note: "Circular-shifts the base monthly demand series by ±N months. Alters the Demand step's base series." },
      { key: "familyUplift", label: "Per-family uplift %", unit: "%",
        min: 0, max: 50, step: 1, perFamily: true,
        note: "Overrides each family's own upside_uplift_pct for the custom scenario. Alters the Demand step's uplift." }
    ]},
    { group: "Supply", levers: [
      { key: "hours", label: "Available hours per resource", unit: "h/mo",
        min: 0, max: 2, step: 0.01, perResource: true, mode: "factor",
        note: "Scales each resource's monthly_available_hours by this factor. Alters the Capacity step's installed hours." },
      { key: "overtime", label: "Overtime hours", unit: "h/mo",
        disabled: true,
        note: "Not modeled — would require an engine-side overtime model (adds hours to effective capacity with a premium cost)." }
    ]},
    { group: "Policy", levers: [
      { key: "rationRule", label: "Rationing rule", unit: "",
        discrete: true, options: ["throughput-per-constraint", "fair-share", "strategic-priority"],
        note: "How scarce hours are allocated when a resource is over capacity. Throughput-per-constraint = the shipped engine rule (descending unit margin); fair-share and strategic-priority are new arithmetic." }
    ]},
    { group: "Financial", levers: [
      { key: "priceDelta", label: "Unit price Δ%", unit: "%",
        min: -50, max: 50, step: 1, perFamily: true,
        note: "Scales each family's unit_price. Alters the Financial step's price AND the rationing sort key (unit_margin)." },
      { key: "vcDelta", label: "Unit variable cost Δ%", unit: "%",
        min: -50, max: 50, step: 1, perFamily: true,
        note: "Scales each family's unit_variable_cost. Alters the Financial step's VC AND the rationing sort key." }
    ]},
    { group: "Inventory", levers: [
      { key: "openingDelta", label: "Opening inventory Δ%", unit: "%",
        min: -50, max: 50, step: 1, perFamily: true,
        note: "Scales each family's opening_inventory_units. Alters the Supply step's opening balance." }
    ]}
  ];
  var TIER2 = [
    { group: "Demand (advanced)", levers: [
      { key: "bias", label: "Forecast bias %", unit: "%", disabled: true, note: "Not in the current data model" },
      { key: "mape", label: "Per-family MAPE override", unit: "%", disabled: true, note: "Stage-4 residual-cone input — SCOPE §5, not yet in this data" }
    ]},
    { group: "Supply (advanced)", levers: [
      { key: "yield", label: "Yield / scrap %", unit: "%", disabled: true, note: "Not modeled — engine assumes 100% yield" },
      { key: "lot", label: "Minimum lot size", unit: "units", disabled: true, note: "Not modeled" }
    ]},
    { group: "Policy (advanced)", levers: [
      { key: "backorder", label: "Backorder vs lost sale", unit: "per family", disabled: true, note: "Engine currently always treats unmet demand as a lost sale — no backorder carry" },
      { key: "buildahead", label: "Build-ahead horizon", unit: "months", disabled: true, note: "Not modeled — supply never exceeds the current month's own demand" }
    ]},
    { group: "Financial (advanced)", levers: [
      { key: "carrying", label: "Inventory carrying %", unit: "%", disabled: true, note: "Not modeled" },
      { key: "otprem", label: "Overtime premium %", unit: "%", disabled: true, note: "Not modeled — no overtime lever yet" },
      { key: "stockpen", label: "Stockout penalty per unit", unit: "$/unit", disabled: true, note: "Not modeled — lost_margin is the only cost of a stockout today" }
    ]},
    { group: "Inventory (advanced)", levers: [
      { key: "maxcap", label: "Max inventory cap", unit: "units", disabled: true, note: "Not modeled — no cap enforced" }
    ]}
  ];

  function leverFmt(lv, value) {
    if (lv.discrete && lv.options) return lv.options[value] || lv.options[0];
    if (lv.perResource) return (value * 100).toFixed(0) + "%";
    if (lv.perFamily) return (value >= 0 ? "+" : "") + value + "%";
    return (value >= 0 ? "+" : "") + value + (lv.unit === "months" ? " mo" : " " + lv.unit);
  }

  function renderLevers(hostId, groups) {
    var host = document.getElementById(hostId);
    host.innerHTML = "";
    groups.forEach(function (g) {
      var wrap = document.createElement("div");
      var t = document.createElement("h3"); t.className = "levergroup__title"; t.textContent = g.group;
      wrap.appendChild(t);
      g.levers.forEach(function (lv) {
        var row = document.createElement("div"); row.className = "lever";
        var head = document.createElement("div"); head.className = "lever__row";
        var lab = document.createElement("span"); lab.className = "lever__label"; lab.textContent = lv.label;
        var un = document.createElement("span"); un.className = "lever__val";
        un.textContent = lv.perResource ? "100%" : (lv.discrete && lv.options ? lv.options[0] : "0");
        head.appendChild(lab); head.appendChild(un);

        var input = document.createElement("input");
        if (lv.disabled) {
          input.type = "range"; input.className = "lever__range"; input.disabled = true;
          input.min = "0"; input.max = "100"; input.value = "50";
          input.setAttribute("aria-label", lv.label + " — not modeled in this engine");
        } else if (lv.discrete && lv.options) {
          input = document.createElement("select"); input.className = "lever__range lever__select";
          lv.options.forEach(function (opt, i) {
            var o = document.createElement("option"); o.value = String(i); o.textContent = opt;
            if (i === 0) o.selected = true;
            input.appendChild(o);
          });
          input.value = "0";
          input.setAttribute("aria-label", lv.label);
        } else {
          input.type = "range"; input.className = "lever__range lever__range--live";
          input.min = String(lv.min !== undefined ? lv.min : -50);
          input.max = String(lv.max !== undefined ? lv.max : 50);
          input.step = String(lv.step !== undefined ? lv.step : 1);
          // hours is a factor on installed capacity; default 1.0 = identity
          input.value = String(lv.perResource ? 1.0 : 0);
          input.setAttribute("aria-label", lv.label);
          if (lv.perResource) input.className += " lever__range--resource";
          if (lv.perFamily) input.className += " lever__range--family";
        }

        // Range sliders fire `input` continuously; a native <select> fires
        // `change` (not `input`) on a user pick. Listen to both.
        input.addEventListener("input", function () { onLeverInput(); });
        input.addEventListener("change", function () { onLeverInput(); });
        function onLeverInput() {
          if (lv.disabled) return;
          LEVER_STATE[lv.key] = Number(input.value);
          un.textContent = leverFmt(lv, LEVER_STATE[lv.key]);
          row.setAttribute("data-dirty", "1");
          applyLeversAndRecompute();
        }

        var note = document.createElement("div"); note.className = "step__subrow"; note.textContent = lv.note;
        row.appendChild(head); row.appendChild(input); row.appendChild(note);
        wrap.appendChild(row);
      });
      host.appendChild(wrap);
    });
  }
  renderLevers("levergroups", TIER1);
  renderLevers("levergroups2", TIER2);

  // Build the levers object for the engine from the current state.
  function collectLevers() {
    var levers = { volMult: 0, seasonShift: 0, rationRule: "throughput-per-constraint",
      hours: {}, familyUplift: {}, priceDeltaPct: {}, vcDeltaPct: {}, openingDeltaPct: {} };
    if (LEVER_STATE.volMult) levers.volMult = LEVER_STATE.volMult;
    if (LEVER_STATE.seasonShift) levers.seasonShift = LEVER_STATE.seasonShift;
    if (LEVER_STATE.rationRule !== undefined) levers.rationRule = ["throughput-per-constraint", "fair-share", "strategic-priority"][LEVER_STATE.rationRule];
    // per-family sliders: a single shared lever maps to every family
    if (LEVER_STATE.familyUplift) D.families.forEach(function (f) { levers.familyUplift[f.id] = LEVER_STATE.familyUplift; });
    if (LEVER_STATE.priceDelta) D.families.forEach(function (f) { levers.priceDeltaPct[f.id] = LEVER_STATE.priceDelta; });
    if (LEVER_STATE.vcDelta) D.families.forEach(function (f) { levers.vcDeltaPct[f.id] = LEVER_STATE.vcDelta; });
    if (LEVER_STATE.openingDelta) D.families.forEach(function (f) { levers.openingDeltaPct[f.id] = LEVER_STATE.openingDelta; });
    // hours lever is a FACTOR on installed capacity; default 1.0 = identity
    D.resources.forEach(function (r) {
      var factor = LEVER_STATE.hours !== undefined ? LEVER_STATE.hours : 1.0;
      levers.hours[r.id] = r.monthly_available_hours * factor;
    });
    return levers;
  }

  function applyLeversAndRecompute() {
    var levers = collectLevers();
    var isDirty = Object.keys(LEVER_STATE).some(function (k) {
      var v = LEVER_STATE[k];
      return v !== undefined && Number(v) !== 0 && (k !== "hours" || Number(v) !== 1.0);
    });
    if (!isDirty) {
      // All levers neutral → custom equals constrained (the shipped engine's
      // constrained scenario, no lever changes).
      D.scenarios.custom = D.scenarios.constrained;
      D.provenance.custom = D.provenance.constrained;
    } else {
      var res = LEVER_ENGINE.recomputeScenario(D, levers, "custom");
      D.scenarios.custom = res.scenario;
      D.provenance.custom = res.provenance;
    }
    focus = "custom";
    A.custom = agg("custom");
    renderComparison();
    renderGrid();
    renderBullets();
    renderFamilies();
    buildTiles();
    buildSummaryTable();
    Array.prototype.forEach.call(document.getElementById("presets").children, function (c, i) {
      c.setAttribute("aria-pressed", String(PRESETS[i].key === focus));
    });
    Array.prototype.forEach.call(tabHost.children, function (c, i) {
      c.setAttribute("aria-pressed", String(SC[i] === focus));
    });
    // The scenario tabs list SC (3 shipped); custom is a focus, not a 4th.
  }

  /* =========================================================================
     SECTION 7 — DRILL-DOWN GRID (m3) + 5-STEP PROVENANCE MODAL (shared)
     ========================================================================= */
  function famList() {
    return D.families.slice().sort(function (a, b) { return b.unit_margin - a.unit_margin; });
  }

  function renderGrid() {
    var t = document.getElementById("grid");
    t.innerHTML = "";
    var fams = famList();
    var head = "<thead><tr><th>Family</th>" + D.month_names.map(function (m) { return "<th>" + m + "</th>"; }).join("") + "</tr></thead>";
    var body = "<tbody>" + fams.map(function (f) {
      var cells = D.month_names.map(function (mn, i) {
        var month = i + 1;
        var entry = D.provenance[focus][f.id][String(month)];
        var sl = entry.supply;
        var unmet = sl.unmet_units > 0;
        return '<td><button class="cell' + (unmet ? " cell--unmet" : "") + '" type="button" data-fam="' + f.id +
          '" data-month="' + month + '" aria-label="' + f.name + " " + mn + " fill rate " + pct(sl.fill_rate * 100, 1) +
          (unmet ? ", " + units(sl.unmet_units) + " units unmet" : "") + '">' + pct(sl.fill_rate * 100, 0) + "</button></td>";
      }).join("");
      return "<tr><td><span class=\"famname\">" + f.name + "</span><span class=\"famsub\">$" + f.unit_margin + " margin/unit</span></td>" + cells + "</tr>";
    }).join("") + "</tbody>";
    t.innerHTML = head + body;

    Array.prototype.forEach.call(t.querySelectorAll(".cell"), function (btn) {
      btn.addEventListener("mousemove", function (e) {
        var fam = btn.getAttribute("data-fam"), month = btn.getAttribute("data-month");
        var f = D.families.filter(function (x) { return x.id === fam; })[0];
        var entry = D.provenance[focus][fam][month];
        var sl = entry.supply;
        showTip(e, f.name + " · " + D.month_names[month - 1],
          [["Demand", units(sl.demand_units) + " u"],
           ["Shipped", units(sl.shipped_units) + " u"],
           ["Unmet", units(sl.unmet_units) + " u"],
           ["Fill rate", pct(sl.fill_rate * 100, 2)]],
          "Click for the full 5-step derivation");
      });
      btn.addEventListener("mouseleave", hideTip);
      btn.addEventListener("click", function () {
        openModal(focus, btn.getAttribute("data-fam"), Number(btn.getAttribute("data-month")));
      });
    });
    document.getElementById("gridnote").textContent =
      "Fill rate by family and month, " + SC_LABEL[focus] + " scenario. Red cells had unmet demand. Every cell drills to its real Demand → Capacity → Rationing → Supply → Financials arithmetic.";
  }

  /* ---- shared modal chrome ---- */
  var scrim = document.getElementById("scrim");
  var modalBody = document.getElementById("modalbody");
  var lastFocus = null;

  function showModal(html) {
    modalBody.innerHTML = html;
    lastFocus = document.activeElement;
    scrim.dataset.open = "1";
    document.getElementById("modalclose").focus();
    document.addEventListener("keydown", onModalKeydown);
    Array.prototype.forEach.call(modalBody.querySelectorAll("[data-drill]"), function (btn) {
      btn.addEventListener("click", function () {
        var parts = btn.getAttribute("data-drill").split("|");
        openModal(parts[0], parts[1], Number(parts[2]));
      });
    });
    Array.prototype.forEach.call(modalBody.querySelectorAll("[data-rollup]"), function (btn) {
      btn.addEventListener("click", function () { openRollup(btn.getAttribute("data-rollup")); });
    });
  }
  function closeModal() {
    scrim.dataset.open = "0";
    document.removeEventListener("keydown", onModalKeydown);
    if (lastFocus) lastFocus.focus();
  }
  function onModalKeydown(e) { if (e.key === "Escape") closeModal(); }
  document.getElementById("modalclose").addEventListener("click", closeModal);
  scrim.addEventListener("click", function (e) { if (e.target === scrim) closeModal(); });

  function stepHtml(num, title, formulaHtml, noteHtml, live) {
    return (
      '<div class="step">' +
        '<div class="step__rail"><div class="step__num' + (live === false ? " step__num--skip" : " step__num--live") + '">' + num + '</div>' +
          '<div class="step-connector"></div></div>' +
        '<div class="step__body"><div class="step__title">' + title + '</div>' +
          (formulaHtml ? '<div class="step__formula">' + formulaHtml + '</div>' : "") +
          (noteHtml ? '<p class="step__note">' + noteHtml + '</p>' : "") +
        '</div>' +
      '</div>'
    );
  }

  function openModal(scenario, famId, month) {
    var f = D.families.filter(function (x) { return x.id === famId; })[0];
    var mn = D.month_names[month - 1];
    var entry = D.provenance[scenario][famId][String(month)];
    var dem = entry.demand, sup = entry.supply, fin = entry.financials;
    var cap = entry.capacity, rat = entry.rationing;

    var html = '<p class="modal__eyebrow">' + SC_LABEL[scenario] + " · " + f.name + " · " + mn + '</p>' +
      '<h2 class="modal__title" id="modaltitle">How ' + pct(sup.fill_rate * 100, 1) + ' fill rate was made</h2>';

    var demFormula = dem.uplift_applied
      ? units(dem.base_units) + " base × (1 + " + pct(dem.uplift_pct * 100, 1) + ") = " + units(dem.demand_units) + " units"
      : units(dem.base_units) + " base, no uplift in " + SC_LABEL[scenario] + " = " + units(dem.demand_units) + " units";
    html += stepHtml(1, "Demand", demFormula, "Base monthly demand for " + f.name + " in " + mn + (dem.uplift_applied ? ", uplifted by this family's own promotion assumption." : "."));

    if (cap.length === 0) {
      html += stepHtml(2, "Capacity", null, f.name + " doesn't share a constrained resource — no RCCP load to check.", false);
    } else {
      var capRows = cap.map(function (c) {
        var rname = D.resources.filter(function (r) { return r.id === c.resource_id; })[0].name;
        return rname + ": " + hrs(c.load_hours) + " load ÷ " + hrs(c.available_hours) + " installed = " + pct(c.utilization_pct, 1) +
          (c.is_bottleneck ? " — OVER installed capacity" : "");
      }).join("<br>");
      html += stepHtml(2, "Capacity", capRows, "Load = every family's demand this month × hours/unit on that resource, summed. Measured against installed hours regardless of scenario (RCCP is a feasibility test, not a decision).");
    }

    if (rat.length === 0) {
      html += stepHtml(3, "Rationing", null, "No shared resource to ration.", false);
    } else {
      var anyConstrained = rat.some(function (r) { return r && r.constrained; });
      var ratRows = rat.map(function (r) {
        if (!r) return "";
        var rname = D.resources.filter(function (x) { return x.id === r.resource_id; })[0].name;
        if (!r.constrained) {
          return rname + ": not over capacity — full ask granted (" + hrs(r.wanted_hours) + ").";
        }
        return rname + ": rank " + r.rank + " of " + r.n_users + " by margin ($" + r.unit_margin + "/unit). " +
          hrs(r.remaining_before_hours) + " hours left before this family → min(" + hrs(r.wanted_hours) + " wanted, " +
          hrs(r.remaining_before_hours) + " left) = " + hrs(r.granted_hours) + " granted → " + hrs(r.remaining_after_hours) + " left for lower-ranked families. " +
          "= " + units2(r.allowed_units) + " units this resource can support.";
      }).join("<br><br>");
      html += stepHtml(3, "Rationing",
        anyConstrained ? ratRows : null,
        anyConstrained
          ? "When a resource is over capacity, " + SC_LABEL[scenario] + " protects the highest-margin business first — greedily, in descending unit-margin order — until hours run out."
          : "Nothing was over capacity this month, so nothing was rationed." + (rat.length ? "<br>" + ratRows : ""),
        anyConstrained);
    }

    var supFormula =
      "Produced = min(what rationing allowed, " + units(dem.demand_units) + " demand) = " + units2(sup.produced_units) + " units<br>" +
      "Shipped = min(" + units2(sup.opening_inventory_units) + " opening + " + units2(sup.produced_units) + " produced, " + units(dem.demand_units) + " demand) = " + units2(sup.shipped_units) + " units<br>" +
      "Unmet = " + units(dem.demand_units) + " demand − " + units2(sup.shipped_units) + " shipped = " + units2(sup.unmet_units) + " units<br>" +
      "Ending inventory = " + units2(sup.opening_inventory_units) + " + " + units2(sup.produced_units) + " − " + units2(sup.shipped_units) + " = " + units2(sup.ending_inventory_units) + " units";
    html += stepHtml(4, "Supply", supFormula, "No backorders: unmet demand this month is a lost sale, not a promise for next month. Ending inventory carries forward as next month's opening balance.");

    var finFormula =
      "Revenue = " + units2(sup.shipped_units) + " shipped × $" + fin.unit_price + " price = " + money2(fin.revenue) + "<br>" +
      "Gross margin = " + units2(sup.shipped_units) + " shipped × $" + fin.unit_margin + " margin/unit = " + money2(fin.gross_margin) +
      (sup.unmet_units > 0 ? "<br>Lost margin = " + units2(sup.unmet_units) + " unmet × $" + fin.unit_margin + " = " + money2(fin.lost_margin) : "") +
      "<br>Inventory value = " + units2(sup.ending_inventory_units) + " ending × $" + fin.unit_variable_cost + " variable cost = " + money2(fin.inventory_value);
    html += stepHtml(5, "Financials", finFormula, null);

    html += '<div class="kpi-tieback"><p class="kpi-tieback__label">Rolls into fill rate</p>' +
      '<p class="kpi-tieback__val">' + units2(sup.shipped_units) + ' ÷ ' + units(dem.demand_units) + ' = ' + pct(sup.fill_rate * 100, 1) + '</p>' +
      '<p class="step__note">This is one family/month; the tiles and reconciliation tables sum this same arithmetic across all families and 12 months.</p></div>';

    showModal(html);
  }

  /* =========================================================================
     SECTION 8 — KPI ROLLUPS (m4 + m5) — aggregates traced to real families
     ========================================================================= */
  function fillRateSummary(scenario) {
    var rows = D.scenarios[scenario].reconciliation;
    var demand = 0, shipped = 0, unmet = 0;
    rows.forEach(function (r) { demand += r.demand_units; shipped += r.shipped_units; unmet += r.unmet_units; });
    return { rows: rows, demand: demand, shipped: shipped, unmet: unmet, fillRate: shipped / demand };
  }

  function familyMonthlyFill(scenario, famId) {
    var p = D.provenance[scenario][famId], out = [];
    for (var m = 1; m <= 12; m++) out.push(p[String(m)].supply.fill_rate * 100);
    return out;
  }
  function fillSvg(series) {
    var W = 200, H = 34, PL = 2, PR = 2, PT = 2, PB = 2;
    var plotW = W - PL - PR, plotH = H - PT - PB;
    var lo = Math.min.apply(null, series) - 2, hi = 100;
    var range = Math.max(1, hi - lo);
    var x = function (i) { return PL + (i / 11) * plotW; };
    var y = function (v) { return PT + plotH - ((v - lo) / range) * plotH; };
    var s = svgEl("svg", { viewBox: "0 0 " + W + " " + H, role: "img" });
    s.appendChild(svgEl("polyline", { fill: "none", stroke: "var(--sop-color-chart-actual)", "stroke-width": 1.5,
      "stroke-opacity": 0.85, "stroke-linejoin": "round", "stroke-linecap": "round",
      points: series.map(function (v, i) { return x(i).toFixed(1) + "," + y(v).toFixed(1); }).join(" ") }));
    s.appendChild(svgEl("line", { x1: PL, y1: y(100), x2: W - PR, y2: y(100), stroke: "var(--sop-color-border-strong)", "stroke-width": 1, "stroke-dasharray": "2 2" }));
    series.forEach(function (v, i) {
      s.appendChild(svgEl("circle", { cx: x(i), cy: y(v), r: 1.6, fill: "var(--sop-color-chart-actual)", "fill-opacity": 0.8 }));
    });
    return s;
  }

  function openFillRateRollup(scenario) {
    var s = fillRateSummary(scenario);
    var html = '<p class="modal__eyebrow">' + SC_LABEL[scenario] + ' · Fill rate rollup</p>' +
      '<h2 class="modal__title" id="modaltitle">How ' + pct(s.fillRate * 100, 1) + ' fill rate was made</h2>';
    var rowsHtml = s.rows.map(function (r) {
      var hi = r.unmet_units > 0 ? " is-highlight" : "";
      return '<tr class="' + hi.trim() + '"><td>' + r.family_name + '</td><td>' + units(r.demand_units) +
        '</td><td>' + units(r.shipped_units) + '</td><td>' + units(r.unmet_units) + '</td><td>' + pct(r.fill_rate_pct, 1) + '</td></tr>';
    }).join("");
    html += '<table class="rolluptable"><thead><tr><th>Family</th><th>Demand</th><th>Shipped</th><th>Unmet</th><th>Fill %</th></tr></thead><tbody>' +
      rowsHtml + '<tr class="is-total"><td>Total</td><td>' + units(s.demand) + '</td><td>' + units(s.shipped) +
      '</td><td>' + units(s.unmet) + '</td><td>' + pct(s.fillRate * 100, 1) + '</td></tr></tbody></table>';
    html += '<div class="rollup-formula">Σ shipped ÷ Σ demand = ' + units(s.shipped) + ' ÷ ' + units(s.demand) + ' = ' + pct(s.fillRate * 100, 1) + '</div>';
    if (scenario === "constrained") {
      var dry = s.rows.filter(function (r) { return r.family_id === "FAM-DRY"; })[0];
      html += '<p class="rollup-note">Dryers are the <strong>only</strong> family with any unmet demand — ' +
        units(dry.unmet_units) + ' units across 3 months (April, May, December). May alone is 65% of it.</p>' +
        '<button type="button" class="rollup-link" data-drill="constrained|FAM-DRY|5">Full derivation for May →</button>';
    }
    if (scenario === "upside") {
      html += '<p class="rollup-note">Assembly Line A exceeds installed capacity in 4 of these 12 months (peak 115% in April) — ' +
        'the same load as Constrained — but Upside ships everything anyway. Upside assumes the gap gets topped up, Constrained does not.</p>' +
        '<button type="button" class="rollup-link" data-rollup="bottleneck">See the capacity curve →</button>';
    }
    showModal(html);
  }

  function openBottleneckRollup() {
    var rid = D.bottleneck.resource_id;
    var resource = D.resources.filter(function (r) { return r.id === rid; })[0];
    var monthly = D.scenarios.constrained.utilization[rid];
    var peak = monthly.reduce(function (a, b) { return b.utilization_pct > a.utilization_pct ? b : a; });
    var html = '<p class="modal__eyebrow">Constrained · ' + resource.name + ' · Capacity rollup</p>' +
      '<h2 class="modal__title" id="modaltitle">How ' + pct(peak.utilization_pct, 1) + ' peak utilization was made</h2>';
    var rowsHtml = monthly.map(function (m) {
      var over = m.utilization_pct > 100;
      var isPeak = m.month === peak.month;
      return '<tr class="' + (over ? "is-highlight" : "") + '"><td>' + D.month_names[m.month - 1] + (isPeak ? " ★" : "") +
        '</td><td>' + hrs(m.load_hours) + '</td><td>' + hrs(m.available_hours) + '</td><td>' + pct(m.utilization_pct, 1) + '</td></tr>';
    }).join("");
    html += '<table class="rolluptable"><thead><tr><th>Month</th><th>Load</th><th>Installed</th><th>Utilization</th></tr></thead><tbody>' + rowsHtml + '</tbody></table>';
    html += '<div class="rollup-formula">Peak = ' + D.month_names[peak.month - 1] + ': ' + hrs(peak.load_hours) + ' load ÷ ' + hrs(peak.available_hours) + ' installed = ' + pct(peak.utilization_pct, 1) + '</div>';
    html += '<p class="rollup-note">Load = every family\'s demand that month × hours/unit on ' + resource.name + ', summed — RCCP is measured against installed hours regardless of scenario. ' +
      resource.name + ' is the only resource that ever breaches capacity: QA and Packaging stay under 93% in every scenario.</p>' +
      '<p class="rollup-note">This exact constraint is what rations Dryers in May — rank 3 of 3 by margin, only 1,128.8 of 1,947.9 hours wanted were granted.</p>' +
      '<button type="button" class="rollup-link" data-drill="constrained|FAM-DRY|5">See that rationing decision →</button>';
    showModal(html);
  }

  function openUpsideValueRollup() {
    var rb = D.scenarios.base.reconciliation, ru = D.scenarios.upside.reconciliation;
    var totalDm = 0, totalDr = 0;
    var rowsHtml = rb.map(function (b, i) {
      var u = ru[i];
      var dm = u.gross_margin - b.gross_margin;
      var dr = u.revenue - b.revenue;
      totalDm += dm; totalDr += dr;
      return '<tr><td>' + b.family_name + '</td><td>' + money(b.gross_margin) + '</td><td>' + money(u.gross_margin) +
        '</td><td>' + money(dm) + '</td><td>' + money(dr) + '</td></tr>';
    }).join("");
    var html = '<p class="modal__eyebrow">Base → Upside · Financial rollup</p>' +
      '<h2 class="modal__title" id="modaltitle">How ' + money(totalDm) + ' margin was unlocked</h2>';
    html += '<table class="rolluptable"><thead><tr><th>Family</th><th>Base margin</th><th>Upside margin</th><th>Δ margin</th><th>Δ revenue</th></tr></thead><tbody>' +
      rowsHtml + '<tr class="is-total"><td>Total</td><td>' + money(D.scenarios.base.summary.total_gross_margin) +
      '</td><td>' + money(D.scenarios.upside.summary.total_gross_margin) + '</td><td>' + money(totalDm) + '</td><td>' + money(totalDr) + '</td></tr></tbody></table>';
    html += '<div class="rollup-formula">ΣUpside margin − ΣBase margin = ' + money(D.scenarios.upside.summary.total_gross_margin) + ' − ' +
      money(D.scenarios.base.summary.total_gross_margin) + ' = ' + money(totalDm) + '<br>Revenue uplift (context, not the headline): ' + money(totalDr) + '</div>';
    html += '<p class="rollup-note">Refrigerators and Washers together are ~80% of the margin uplift. Upside assumes every family\'s own upside_uplift_pct demand ships in full.</p>';
    showModal(html);
  }

  function openMarginAtRiskRollup() {
    var months = [4, 5, 12];
    var total = 0;
    var rowsHtml = months.map(function (m) {
      var sl = D.provenance.constrained["FAM-DRY"][String(m)].supply;
      var lost = sl.unmet_units * D.provenance.constrained["FAM-DRY"][String(m)].financials.unit_margin;
      total += lost;
      return '<tr><td><button type="button" class="rowbtn" data-drill="constrained|FAM-DRY|' + m + '">' + D.month_names[m - 1] + '</button></td>' +
        '<td>' + units2(sl.unmet_units) + '</td><td>$' + D.provenance.constrained["FAM-DRY"][String(m)].financials.unit_margin + '</td><td>' + money2(lost) + '</td></tr>';
    }).join("");
    var html = '<p class="modal__eyebrow">Constrained · Dryers · Financial-risk rollup</p>' +
      '<h2 class="modal__title" id="modaltitle">How ' + money2(total) + ' margin at risk was made</h2>';
    html += '<table class="rolluptable"><thead><tr><th>Month</th><th>Unmet units</th><th>Unit margin</th><th>Lost margin</th></tr></thead><tbody>' +
      rowsHtml + '<tr class="is-total"><td>Total</td><td></td><td></td><td>' + money2(total) + '</td></tr></tbody></table>';
    html += '<p class="rollup-note">Other 9 months: fully served, $0 lost margin. Dryers are the only family that loses anything in Constrained — see the Bottleneck rollup for why Assembly Line A picks Dryers last.</p>' +
      '<button type="button" class="rollup-link" data-rollup="bottleneck">Why Assembly Line A rations Dryers →</button>';
    showModal(html);
  }

  function openBaseRollup() {
    var rows = D.scenarios.base.reconciliation;
    var tot = 0;
    var rowsHtml = rows.map(function (r) { tot += r.gross_margin; return '<tr><td>' + r.family_name + '</td><td>' + money(r.gross_margin) + '</td></tr>'; }).join("");
    var html = '<p class="modal__eyebrow">Base · Financial rollup</p>' +
      '<h2 class="modal__title" id="modaltitle">How ' + money(D.scenarios.base.summary.total_gross_margin) + ' base margin was made</h2>';
    html += '<table class="rolluptable"><thead><tr><th>Family</th><th>Margin</th></tr></thead><tbody>' +
      rowsHtml + '<tr class="is-total"><td>Total</td><td>' + money(tot) + '</td></tr></tbody></table>';
    html += '<div class="rollup-formula">Σ margin per family = ' + money(tot) + ' = Base total</div>';
    showModal(html);
  }

  function openConstrainedRollup() {
    var rows = D.scenarios.constrained.reconciliation;
    var tot = 0;
    var rowsHtml = rows.map(function (r) { tot += r.gross_margin; return '<tr><td>' + r.family_name + '</td><td>' + money(r.gross_margin) + '</td></tr>'; }).join("");
    var html = '<p class="modal__eyebrow">Constrained · Financial rollup</p>' +
      '<h2 class="modal__title" id="modaltitle">How ' + money(D.scenarios.constrained.summary.total_gross_margin) + ' realized margin was made</h2>';
    html += '<table class="rolluptable"><thead><tr><th>Family</th><th>Margin</th></tr></thead><tbody>' +
      rowsHtml + '<tr class="is-total"><td>Total</td><td>' + money(tot) + '</td></tr></tbody></table>';
    html += '<p class="rollup-note">Constrained ships less Dryers (Apr/May/Dec shortfall) — that is the ▼ constrained penalty in the waterfall.</p>';
    html += '<div class="rollup-formula">Σ margin per family = ' + money(tot) + ' = Realized total</div>';
    showModal(html);
  }

  function openWaterfallRollup() {
    var b = D.scenarios.base.summary, u = D.scenarios.upside.summary, c = D.scenarios.constrained.summary;
    var lift = u.total_gross_margin - b.total_gross_margin, penalty = c.total_lost_margin;
    var html = '<p class="modal__eyebrow">Margin waterfall · Bridge rollup</p>' +
      '<h2 class="modal__title" id="modaltitle">How ' + money(c.total_gross_margin) + ' realized margin was made</h2>';
    html += '<table class="rolluptable"><thead><tr><th>Step</th><th>Value</th></tr></thead><tbody>' +
      '<tr><td>Base</td><td>' + money(b.total_gross_margin) + '</td></tr>' +
      '<tr><td>Upside lift (▲)</td><td>' + money(lift) + '</td></tr>' +
      '<tr><td>Constrained penalty (▼)</td><td>' + money2(penalty) + '</td></tr>' +
      '<tr class="is-total"><td>Net</td><td>' + money(c.total_gross_margin) + '</td></tr></tbody></table>';
    html += '<div class="rollup-formula">Base ' + money(b.total_gross_margin) + ' + lift ' + money(lift) + ' − penalty ' + money2(penalty) + ' = realized ' + money(c.total_gross_margin) + '</div>';
    showModal(html);
  }

  function openRollup(kind) {
    if (kind === "waterfall") return openWaterfallRollup();
    if (kind === "bottleneck") return openBottleneckRollup();
    if (kind === "upside-value") return openUpsideValueRollup();
    if (kind === "margin-at-risk") return openMarginAtRiskRollup();
    if (kind.indexOf("fillrate-") === 0) return openFillRateRollup(kind.slice("fillrate-".length));
  }

  /* =========================================================================
     SECTION 9 — KPI PANELS (m4): fill bullets, load curve, margin months,
     upside variance
     ========================================================================= */
  function animateCount(el, to, fmt, ms) {
    var t0 = null;
    var dur = ms || 700;
    function frame(t) {
      if (!t0) t0 = t;
      var p = Math.min(1, (t - t0) / dur);
      var eased = 1 - Math.pow(1 - p, 3);
      el.textContent = fmt(to * eased);
      if (p < 1) requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
  }

  function perFamilyRows(scenario, rows) {
    var lines = rows.slice().sort(function (a, b) { return b.unmet_units - a.unmet_units; })
      .slice(0, 5)
      .map(function (r) { return r.family_name + " " + pct(r.fill_rate_pct, 1) + (r.unmet_units > 0 ? " · " + units(r.unmet_units) + " unmet" : ""); });
    return lines.join("<br>");
  }

  function buildPanelNotes() {
    var base = D.scenarios.base.summary, up = D.scenarios.upside.summary, con = D.scenarios.constrained.summary;
    var totalLost = con.total_lost_margin, lift = up.total_gross_margin - base.total_gross_margin;
    document.getElementById("fillnote").innerHTML =
      "Every scenario except <strong>Constrained</strong> ships everything — only Dryers fall short, and only <strong>3 months of the year</strong>." +
      ' <span class="delta delta--good">▲ <span class="num-anim">' + money(lift) + '</span></span> is the margin upside; ' +
      ' <span class="delta delta--bad">▼ <span class="num-anim">' + money2(totalLost) + '</span></span> is what Constrained would leave on the table. Hover a bullet for the monthly story.';
    var pk = peakMonth();
    document.getElementById("loadnote").innerHTML =
      'One resource ever breaches capacity: <strong>' + resName(D.bottleneck.resource_id) + '</strong>, peaking at ' +
      '<strong>' + pct(pk.utilization_pct, 1) + '</strong> in ' + D.month_names[pk.month - 1] +
      ' — the constraint that rations <strong>Dryers</strong> in Apr · May · Dec. Click for the 12-month table.';
    document.getElementById("marginnote").innerHTML =
      'Dryers lose <strong>' + money2(totalLost) + '</strong> — all of it in <strong>April, May and December</strong>; the other nine months cost nothing.';
    document.getElementById("upsidenote").innerHTML =
      'Upside banks <strong>▲ ' + money(lift) + '</strong> margin over Base' +
      ' — Refrigerators and Washers are <strong>~80%</strong> of the uplift. Margin is the KPI; revenue is context.';
  }

  function wireDrill(id, fn) {
    var el = document.getElementById(id);
    if (el) el.addEventListener("click", function (e) { e.stopPropagation(); fn(); });
  }

  var fillPop = document.createElement("div");
  fillPop.className = "fillpop"; fillPop.setAttribute("role", "status");
  document.body.appendChild(fillPop);

  function showFillPop(evt, sid) {
    var s = fillRateSummary(sid);
    var famWithData = s.rows.map(function (r) { return r.family_id; });
    var series = familyMonthlyFill(sid, famWithData[0]);
    var top = s.rows.slice().sort(function (a, b) { return b.unmet_units - a.unmet_units; })[0];
    var topName = top.family_name, topFill = pct(top.fill_rate_pct, 1);
    fillPop.innerHTML = "";
    var head = document.createElement("div"); head.className = "fillpop__head";
    head.textContent = SC_LABEL[sid] + " · monthly fill";
    fillPop.appendChild(head);
    fillPop.appendChild(fillSvg(series));
    var note = document.createElement("p");
    note.style.cssText = "font-size:var(--sop-text-small);color:var(--sop-color-text-secondary);margin:6px 0 0;line-height:1.5;";
    note.innerHTML = "Worst month: " + topName + " at " + topFill + (top.unmet_units > 0 ? " — " + units(top.unmet_units) + " units short" : "");
    fillPop.appendChild(note);
    fillPop.dataset.show = "1";
    var x = evt.clientX + 14, y = evt.clientY - fillPop.offsetHeight - 10;
    if (y < 6) y = evt.clientY + 14;
    if (x + 226 > window.innerWidth) x = window.innerWidth - 226;
    fillPop.style.left = x + "px"; fillPop.style.top = y + "px";
  }
  function hideFillPop() { fillPop.dataset.show = "0"; }

  function buildFillBullets() {
    var host = document.getElementById("fillrow");
    host.innerHTML = "";
    var con = fillRateSummary("constrained");
    var dryUnmet = con.rows.filter(function (r) { return r.family_id === "FAM-DRY"; })[0].unmet_units;
    var totalLost = D.scenarios.constrained.summary.total_lost_margin;
    ["base", "upside", "constrained"].forEach(function (sid) {
      var s = fillRateSummary(sid);
      var wrap = document.createElement("div"); wrap.className = "bullet clickable";
      var head = document.createElement("div"); head.className = "bullet__head";
      var nm = document.createElement("span"); nm.className = "bullet__name"; nm.textContent = SC_LABEL[sid];
      var sub = document.createElement("span"); sub.className = "bullet__sub";
      sub.textContent = s.unmet > 0 ? units(dryUnmet) + " unmet · −" + money2(totalLost) : "0 unmet";
      head.appendChild(nm); head.appendChild(sub); wrap.appendChild(head);
      var chart = bulletSvg(s.fillRate * 100, 100, 100, "full fill", function (v) { return pct(v, 1); }, sid, []);
      wrap.appendChild(chart);
      var tipLong = SC_LABEL[sid] + " fill rate " + pct(s.fillRate * 100, 2) + " — " +
        (s.unmet > 0 ? units(dryUnmet) + " units unmet (Dryers)" : "everything shipped") +
        "<br>" + perFamilyRows(sid, s.rows) + "<br>Click for the rollup";
      wrap.addEventListener("click", function () { openFillRateRollup(sid); });
      wrap.addEventListener("mouseenter", function (e) { showTip(e, tipLong); showFillPop(e, sid); });
      wrap.addEventListener("mousemove", function (e) { showTip(e, tipLong); showFillPop(e, sid); });
      wrap.addEventListener("mouseleave", function () { hideTip(); hideFillPop(); });
      host.appendChild(wrap);
    });
  }

  function drawLoadCurve() {
    var data = lineA(), pk = peakMonth(), maxScale = 125;
    var BW = 520, BH = 150, PL = 8, PR = 8, PT = 16, PB = 22;
    var plotW = BW - PL - PR, plotH = BH - PT - PB, slot = plotW / 12, bw = slot * 0.6;
    var cx = function (i) { return PL + (i + 0.5) * slot; };
    var y = function (v) { return PT + plotH - (Math.min(v, maxScale) / maxScale) * plotH; };
    var svg = svgEl("svg", { viewBox: "0 0 " + BW + " " + BH, role: "img" });
    var prev = 0;
    BANDS.forEach(function (b) {
      svg.appendChild(svgEl("rect", { x: PL, y: y(b.to), width: plotW, height: y(prev) - y(b.to), fill: b.fill }));
      prev = b.to;
    });
    svg.appendChild(svgEl("line", { x1: PL, y1: y(100), x2: BW - PR, y2: y(100), class: "ref-line" }));
    var cap = svgEl("text", { x: BW - PR, y: y(100) - 4, class: "tick-text", "text-anchor": "end" });
    cap.textContent = "installed capacity (100%)"; svg.appendChild(cap);
    var RATION = [4, 5, 12];
    data.forEach(function (m, i) {
      var over = m.utilization_pct > 100;
      var ration = RATION.indexOf(m.month) !== -1;
      svg.appendChild(svgEl("rect", { x: cx(i) - bw / 2, y: y(m.utilization_pct), width: bw, height: PT + plotH - y(m.utilization_pct), rx: 1,
        fill: over ? "var(--sop-color-bad)" : "var(--sop-color-chart-actual)", "fill-opacity": over ? 0.9 : 0.8 }));
      if (m.month === pk.month) {
        var lab = svgEl("text", { x: cx(i), y: y(m.utilization_pct) - 5, class: "bar-value", "text-anchor": "middle", fill: "var(--sop-color-bad)" });
        lab.textContent = pct(m.utilization_pct, 1); svg.appendChild(lab);
      }
      if (ration) {
        svg.appendChild(svgEl("rect", { x: cx(i) - slot / 2, y: PT + plotH + 3, width: slot, height: 3, rx: 1, class: "mflag mflag--ration track" }));
        var rl = svgEl("text", { x: cx(i), y: BH - 8, class: "mflag mflag--ration", "text-anchor": "middle", "font-size": 9 });
        rl.textContent = "·"; svg.appendChild(rl);
      }
      var ml = svgEl("text", { x: cx(i), y: BH - 6, class: "tick-text", "text-anchor": "middle" });
      ml.textContent = D.month_names[m.month - 1].slice(0, 1); svg.appendChild(ml);
      var hit = svgEl("rect", { x: cx(i) - slot / 2, y: PT, width: slot, height: plotH + 8, class: "mark-hit" });
      hit.addEventListener("mousemove", function (e) {
        showTip(e, D.month_names[m.month - 1] + ": " + hrs(m.load_hours) + " load ÷ " + hrs(m.available_hours) + " = " + pct(m.utilization_pct, 1) + (over ? " — OVER capacity" : "") + (ration ? " · rations Dryers" : ""));
      });
      hit.addEventListener("mouseleave", hideTip); svg.appendChild(hit);
    });
    var wrap = document.getElementById("loadwrap"); wrap.innerHTML = ""; wrap.appendChild(svg);
    var lnote = document.createElement("p"); lnote.className = "chartnote";
    lnote.textContent = "Apr · May · Dec over 100% — the only months that cost shipped units.";
    wrap.appendChild(lnote);
    wrap.addEventListener("click", function () { openBottleneckRollup(); });
  }

  function drawMarginMonths() {
    var rows = [4, 5, 12].map(function (mo) {
      var entry = D.provenance.constrained["FAM-DRY"][String(mo)];
      return { month: mo, unmet: entry.supply.unmet_units, um: entry.financials.unit_margin,
               lost: entry.supply.unmet_units * entry.financials.unit_margin };
    });
    var total = rows.reduce(function (a, r) { return a + r.lost; }, 0);
    var max = Math.max.apply(null, rows.map(function (r) { return r.lost; })) || 1;
    var BW = 360, BH = 130, PL = 8, PR = 8, PT = 16, PB = 22;
    var plotW = BW - PL - PR, plotH = BH - PT - PB, slot = plotW / rows.length, bw = slot * 0.5;
    var cx = function (i) { return PL + (i + 0.5) * slot; };
    var y = function (v) { return PT + plotH - (v / max) * plotH; };
    var svg = svgEl("svg", { viewBox: "0 0 " + BW + " " + BH, role: "img" });
    svg.appendChild(svgEl("line", { x1: PL, y1: PT + plotH, x2: BW - PR, y2: PT + plotH, class: "axis-line" }));
    rows.forEach(function (r, i) {
      var bar = svgEl("rect", { x: cx(i) - bw / 2, y: y(r.lost), width: bw, height: PT + plotH - y(r.lost), rx: 1, fill: "var(--sop-color-bad)", "fill-opacity": 0.85 });
      bar.classList.add("rise", "rise--" + (i + 1)); svg.appendChild(bar);
      var vl = svgEl("text", { x: cx(i), y: y(r.lost) - 5, class: "bar-value", "text-anchor": "middle", fill: "var(--sop-color-bad)" });
      var n = svgEl("tspan", {}); vl.appendChild(n);
      animateCount(n, r.lost, function (v) { return money(v); }, 600);
      svg.appendChild(vl);
      var ml = svgEl("text", { x: cx(i), y: BH - 6, class: "tick-text", "text-anchor": "middle" });
      ml.textContent = D.month_names[r.month - 1]; svg.appendChild(ml);
      var hit = svgEl("rect", { x: cx(i) - slot / 2, y: PT, width: slot, height: plotH, class: "mark-hit" });
      hit.addEventListener("mousemove", function (e) {
        showTip(e, D.month_names[r.month - 1] + " · Dryers: " + units2(r.unmet) + " unmet × $" + r.um + " = " + money2(r.lost) + " lost");
      });
      hit.addEventListener("mouseleave", hideTip); svg.appendChild(hit);
    });
    var wrap = document.getElementById("marginwrap"); wrap.innerHTML = ""; wrap.appendChild(svg);
    var note = document.createElement("p"); note.className = "chartnote";
    note.textContent = "0 lost margin in the other 9 months. Total at risk: " + money2(total) + ".";
    wrap.appendChild(note);
    wrap.addEventListener("click", function () { openMarginAtRiskRollup(); });
  }

  function drawUpsideVariance() {
    var base = D.scenarios.base.summary.total_gross_margin, up = D.scenarios.upside.summary.total_gross_margin;
    var BW = 460, BH = 70, GUT = 74, PR = 74, ROWH = 18, GAP = 4;
    var hi = up * 1.02 || 1, plotW = BW - GUT - PR;
    var x = function (v) { return GUT + (v / hi) * plotW; };
    var svg = svgEl("svg", { viewBox: "0 0 " + BW + " " + BH, role: "img" });
    [["base", base], ["upside", up]].forEach(function (r, i) {
      var sid = r[0], v = r[1], yy = i * (ROWH + GAP) + 2;
      var lab = svgEl("text", { x: GUT - 8, y: yy + ROWH / 2 + 3.5, class: "bar-label", "text-anchor": "end" });
      lab.textContent = SC_LABEL[sid]; svg.appendChild(lab);
      var w = Math.max(0, x(v) - GUT);
      if (w > 0.5) {
        var bar = svgEl("rect", { x: GUT, y: yy, width: w, height: ROWH, rx: 1 });
        if (sid === "upside") bar.classList.add("rise", "rise--" + (i + 1));
        paintScenario(bar, sid); svg.appendChild(bar);
      }
      var vl = svgEl("text", { x: GUT + w + 6, y: yy + ROWH / 2 + 3.5, class: "bar-value" });
      if (sid === "upside") {
        var n = svgEl("tspan", {}); vl.appendChild(n);
        animateCount(n, v, function (x) { return money(x); }, 700);
      } else { vl.textContent = money(v); }
      svg.appendChild(vl);
      var hit = svgEl("rect", { x: 0, y: yy, width: BW, height: ROWH, class: "mark-hit" });
      hit.addEventListener("mousemove", function (e) {
        showTip(e, SC_LABEL[sid] + " gross margin " + money2(v) + (sid === "base" ? "" : "  (+" + money2(v - base) + " vs Base)"));
      });
      hit.addEventListener("mouseleave", hideTip); svg.appendChild(hit);
    });
    svg.appendChild(svgEl("line", { x1: GUT, y1: 0, x2: GUT, y2: BH - 10, class: "axis-line" }));
    var wrap = document.getElementById("upsidewrap"); wrap.innerHTML = ""; wrap.appendChild(svg);
    var dm = up - base, dr = D.scenarios.upside.summary.total_revenue - D.scenarios.base.summary.total_revenue;
    var note = document.createElement("p"); note.className = "chartnote";
    note.innerHTML = '<span class="delta delta--good">▲ ' + money(dm) + '</span> margin &middot; <span class="delta delta--good">▲ ' + money(dr) + '</span> revenue (context). Margin is the KPI.';
    wrap.appendChild(note);
    wrap.addEventListener("click", function () { openUpsideValueRollup(); });
  }

  /* =========================================================================
     SECTION 10 — MARGIN WATERFALL (m5)
     ========================================================================= */
  function buildWaterfall() {
    var b = D.scenarios.base.summary, u = D.scenarios.upside.summary, c = D.scenarios.constrained.summary;
    var WF = {
      base: b.total_gross_margin,
      lift: u.total_gross_margin - b.total_gross_margin,
      penalty: c.total_lost_margin,
      realized: c.total_gross_margin
    };
    var steps = [
      { key: "base", label: "Base", val: WF.base, kind: "base" },
      { key: "lift", label: "+ Upside lift", val: WF.lift, kind: "up" },
      { key: "penalty", label: "− Constrained penalty", val: -WF.penalty, kind: "pen" },
      { key: "real", label: "Realized — Constrained", val: WF.realized, kind: "real" }
    ];
    var svg = document.getElementById("wfsvg");
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    var W = 760, H = 300, PL = 70, PR = 20, PT = 30, PB = 50;
    var plotW = W - PL - PR, plotH = H - PT - PB;
    var max = WF.base * 1.05;
    var min = Math.min(0, -WF.penalty) * 1.15;
    var span = (max - min) || 1;
    var y = function (v) { return PT + plotH - ((v - min) / span) * plotH; };
    var slot = plotW / steps.length, bw = Math.min(slot * 0.62, 96), gutter = slot * 0.18;

    svg.appendChild(svgEl("line", { x1: PL, y1: y(0), x2: W - PR, y2: y(0), class: "wf__baseline" }));
    [0, max, min].forEach(function (v) {
      var t = svgEl("text", { x: PL - 8, y: y(v) + 4, class: "wf__axislabel", "text-anchor": "end" });
      t.textContent = money(v); svg.appendChild(t);
    });

    var cursor = WF.base;
    steps.forEach(function (st, i) {
      var cx = PL + (i + 0.5) * slot;
      var isDelta = st.kind === "up" || st.kind === "pen";
      var isTotal = st.kind === "real";
      var top = isDelta ? cursor : 0;
      var bottom = isDelta ? cursor + st.val : st.val;
      var yy = Math.min(y(top), y(bottom));
      var h = Math.abs(y(bottom) - y(top));
      var fill = st.kind === "base" ? "var(--sop-color-ink)"
        : st.kind === "up" ? "var(--sop-color-good)"
        : st.kind === "pen" ? "var(--sop-color-bad)"
        : "var(--sop-color-info)";
      var bar = svgEl("rect", { x: cx - bw / 2, y: yy, width: bw, height: Math.max(1, h),
        rx: st.kind === "pen" ? 0 : 4, fill: fill, "fill-opacity": st.kind === "real" ? 0.9 : 0.85 });
      svg.appendChild(bar);
      if (i > 0) {
        var prevEnd = PL + (i - 1 + 0.5) * slot + bw / 2 + gutter;
        var connStart = cx - bw / 2 - gutter;
        svg.appendChild(svgEl("line", { x1: prevEnd, y1: y(cursor), x2: connStart, y2: y(cursor), class: "wf__connector" }));
        if (st.kind === "pen") {
          svg.appendChild(svgEl("line", { x1: cx, y1: y(0), x2: cx, y2: y(cursor), class: "wf__connector" }));
        }
      }
      var valY = st.kind === "pen" ? Math.max(y(bottom) + 14, y(top) + 12) : y(top) - 8;
      var onColor = st.kind === "up" || st.kind === "pen" || st.kind === "real";
      var onLight = st.kind === "base";
      var cls = onColor ? "wf__label-on-bar" : (onLight ? "wf__label-on-light" : "wf__stepval");
      var vl = svgEl("text", { x: cx, y: valY, class: cls, "text-anchor": "middle" });
      vl.textContent = (st.kind === "up" ? "▲ " : st.kind === "pen" ? "▼ " : "") + (st.kind === "pen" ? money2(Math.abs(st.val)) : money(st.val));
      svg.appendChild(vl);
      var lab = svgEl("text", { x: cx, y: H - 28, class: "wf__steplabel", "text-anchor": "middle" });
      lab.textContent = st.label; svg.appendChild(lab);
      var hit = svgEl("rect", { x: cx - slot / 2, y: PT, width: slot, height: plotH, class: "mark-hit" });
      (function (st2) {
        hit.addEventListener("mousemove", function (e) {
          showTip(e, st2.label + ": " + money2(Math.abs(st2.val)) + " · click for the rollup");
        });
        hit.addEventListener("mouseleave", hideTip);
        hit.addEventListener("click", function () {
          if (st2.kind === "up") openUpsideValueRollup();
          else if (st2.kind === "pen") openMarginAtRiskRollup();
          else if (st2.kind === "base") openBaseRollup();
          else openConstrainedRollup();
        });
      })(st);
      svg.appendChild(hit);
      if (isDelta || isTotal) cursor += st.val;
    });
  }

  function buildBridgeTable() {
    var b = D.scenarios.base.summary, u = D.scenarios.upside.summary, c = D.scenarios.constrained.summary;
    var WF = {
      base: b.total_gross_margin,
      lift: u.total_gross_margin - b.total_gross_margin,
      penalty: c.total_lost_margin,
      realized: c.total_gross_margin
    };
    var tb = document.querySelector("#bridgetable tbody");
    tb.innerHTML = "";
    var rows = [
      { label: "Base margin (plan)", val: WF.base, kind: "base", extra: "See how →" },
      { label: "Upside lift (▲)", val: WF.lift, kind: "up", extra: "Upside − Base" },
      { label: "Constrained penalty (▼)", val: WF.penalty, kind: "pen", extra: "Dryers, 3 months" },
      { label: "Realized — Constrained", val: WF.realized, kind: "real", extra: "Recommended plan" }
    ];
    rows.forEach(function (r) {
      var tr = document.createElement("tr");
      var td1 = document.createElement("td"); td1.textContent = r.label; tr.appendChild(td1);
      var td2 = document.createElement("td"); td2.className = r.kind === "up" ? "wf__val-good" : r.kind === "pen" ? "wf__val-bad" : "";
      td2.textContent = (r.kind === "up" ? "▲ " : r.kind === "pen" ? "▼ " : "") + (r.kind === "pen" ? money2(r.val) : money(r.val));
      tr.appendChild(td2);
      var td3 = document.createElement("td");
      var btn = document.createElement("button"); btn.type = "button"; btn.className = "wf__cellclick";
      btn.textContent = r.extra;
      (function (kind) {
        btn.addEventListener("click", function () {
          if (kind === "up") openUpsideValueRollup();
          else if (kind === "pen") openMarginAtRiskRollup();
          else if (kind === "base") openBaseRollup();
          else openConstrainedRollup();
        });
      })(r.kind);
      td3.appendChild(btn); tr.appendChild(td3);
      tb.appendChild(tr);
    });
    var tot = document.createElement("tr"); tot.className = "is-total";
    var t1 = document.createElement("td"); t1.textContent = "Net check";
    var t2 = document.createElement("td"); t2.className = "wf__val-good"; t2.textContent = money(WF.realized);
    var t3 = document.createElement("td"); t3.textContent = money(WF.base) + " + " + money(WF.lift) + " − " + money2(WF.penalty) + " = " + money(WF.realized);
    tot.appendChild(t1); tot.appendChild(t2); tot.appendChild(t3); tb.appendChild(tot);
  }

  /* =========================================================================
     SECTION 11 — TABLE COLLAPSE (m1 summary table) + LEGEND
     ========================================================================= */
  function buildSummaryTable() {
    var t = document.getElementById("table");
    var head = "<thead><tr><th>Metric</th>" + SC.map(function (s) { return "<th>" + SC_LABEL[s] + "</th>"; }).join("") + "</tr></thead>";
    var metrics = [
      ["Revenue", function (s) { return money(s.total_revenue); }],
      ["Gross margin", function (s) { return money(s.total_gross_margin); }],
      ["Lost revenue", function (s) { return money(s.total_lost_revenue); }],
      ["Lost margin", function (s) { return money(s.total_lost_margin); }],
      ["Ending inventory (at cost)", function (s) { return money(s.ending_inventory_value); }],
      ["Fill rate", function (s) { return pct(s.fill_rate * 100, 2); }]
    ];
    var body = "<tbody>" + metrics.map(function (m) {
      return "<tr><td>" + m[0] + "</td>" + SC.map(function (s) {
        return "<td>" + m[1](D.scenarios[s].summary) + "</td>";
      }).join("") + "</tr>";
    }).join("") + "</tbody>";
    t.innerHTML = head + body;
  }

  function buildLegend() {
    var lg = document.getElementById("legend");
    [
      { html: '<span class="legend__swatch" style="background:var(--sop-color-chart-actual);opacity:0.85"></span>', text: "Base — solid" },
      { html: '<span class="legend__swatch" style="background:var(--sop-color-ink-soft)"></span>', text: "Upside — light solid" },
      { html: '<svg class="legend__swatch" viewBox="0 0 20 11"><rect width="20" height="11" fill="url(#hatch)"/></svg>', text: "Constrained — hatched" },
      { html: '<span class="legend__swatch" style="background:var(--sop-color-brand);opacity:0.85"></span>', text: "Custom (levers) — brand" },
      { html: '<span class="legend__swatch" style="border:1px solid var(--sop-color-ink-soft)"></span>', text: "Demand (plan) — outline" },
      { html: '<span class="legend__swatch" style="background:var(--sop-color-bad)"></span>', text: "unmet demand" },
      { html: '<span class="delta delta--good">▲</span>', text: "better than Base" },
      { html: '<span class="delta delta--bad">▼</span>', text: "worse than Base" }
    ].forEach(function (it) {
      var d = document.createElement("span"); d.className = "legend__item";
      d.innerHTML = it.html + "<span>" + it.text + "</span>";
      lg.appendChild(d);
    });
  }

  var tw = document.getElementById("tablewrap"), tb = document.getElementById("tabletoggle");
  tb.addEventListener("click", function () {
    var open = tw.hasAttribute("hidden");
    if (open) tw.removeAttribute("hidden"); else tw.setAttribute("hidden", "");
    tb.setAttribute("aria-expanded", String(open));
    tb.textContent = open ? "Hide table" : "Show table";
  });

  /* =========================================================================
     SECTION 12 — NARRATIVE RAIL (m1)
     ========================================================================= */
  function buildRail() {
    var bn = D.bottleneck;
    var con = D.scenarios.constrained.summary;
    var worstMonth = D.scenarios.constrained.monthly.reduce(function (a, b) { return b.unmet > a.unmet ? b : a; });
    var overCap = D.scenarios.constrained.utilization[bn.resource_id].filter(function (r) { return r.utilization_pct > 100; });
    var findings = [
      { dot: "warn", html: "<strong>" + bn.resource_name + "</strong> runs over capacity in <strong>" +
          overCap.length + " of 12 months</strong>, peaking at " + pct(bn.utilization_pct) + " in " + bn.month_name + "." },
      { dot: "bad", html: "Worst shortfall is <strong>" + worstMonth.name + "</strong> — " +
          units(worstMonth.unmet) + " units unserved, " + money(worstMonth.lost_margin) + " of margin lost." },
      { dot: "good", html: "Fill rate holds at <strong>" + pct(con.fill_rate * 100, 2) +
          "</strong>; the shortfall is concentrated, not spread across the year." },
      { dot: "info", html: "Base and Upside both clear demand fully by construction — they carry <strong>no capacity check</strong>. Only Constrained is buildable." }
    ];
    var fh = document.getElementById("findings");
    findings.forEach(function (f) {
      var li = document.createElement("li"); li.className = "rail__item";
      var d = document.createElement("span"); d.className = "dot dot--" + f.dot;
      var t = document.createElement("span"); t.innerHTML = f.html;
      li.appendChild(d); li.appendChild(t); fh.appendChild(li);
    });
    document.getElementById("assumptions").innerHTML =
      "Upside applies a per-family uplift to Base demand. Constrained rations the same demand against " +
      D.resources.length + " finite resources, in unit-margin order. Inventory is carried at variable cost. " +
      "No optimiser runs — rationing is a priority rule, and it is visible.";
  }

  /* =========================================================================
     INIT
     ========================================================================= */
  buildHeadline();
  buildTiles();
  buildSmallMultiples();
  buildPresets();
  renderComparison();
  renderGrid();
  buildPanelNotes();
  buildFillBullets();
  drawLoadCurve();
  drawMarginMonths();
  drawUpsideVariance();
  wireDrill("margindrill", openMarginAtRiskRollup);
  wireDrill("upsidedrill", openUpsideValueRollup);
  buildWaterfall();
  buildBridgeTable();
  buildSummaryTable();
  buildLegend();
  buildRail();

  document.getElementById("prov").textContent =
    D.families.length + " families · " + D.resources.length + " resources · 12 monthly buckets · every figure from the engine";
  document.getElementById("stamp").textContent = "Generated " + new Date(D.generated_at).toLocaleString();
})();

</script>
</body>
</html>"""


def render_dashboard(context: dict, out_path: Path | str) -> None:
    """Render the self-contained cockpit HTML, embedding `context` once."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    data_json = json.dumps(context, ensure_ascii=False).replace("</", "<\\/")
    html_doc = _TEMPLATE.replace("__DATA_JSON__", data_json)
    out_path.write_text(html_doc, encoding="utf-8")
