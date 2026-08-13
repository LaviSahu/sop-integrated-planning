"""Emit mockups/data.js from the real engine — no hand-typed numbers anywhere.

Every figure a mockup renders comes from here, so a reviewer can re-derive it by
running the engine. Regenerate with:

    PYTHONPATH=src python3 mockups/build_data.py

`build_context()` is deliberately not reused: it exposes monthly totals in UNITS
only, and the mockups need monthly revenue and margin too. Those are aggregated
here straight off the per-(family, month) FinanceLines the engine already builds.

`_provenance()` (added for mockup 3's 5-step drill-down modal) goes one level
deeper still: per (scenario, family, month) it exposes the actual Demand ->
Capacity -> Rationing -> Supply -> Financials arithmetic. The rationing step
calls constrain.py's own `_allowed_units_this_month` (the private function that
already IS the authoritative rationing decision) rather than re-deriving the
greedy-by-margin allocation independently — only the presentational trail
(rank order, cumulative/remaining hours) is recomputed here, straight off that
authoritative result, so there is exactly one place the rationing rule lives.
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from sop_integrated_planning import capacity as capacity_mod
from sop_integrated_planning import cli
from sop_integrated_planning import constrain as constrain_mod
from sop_integrated_planning import demand as demand_mod
from sop_integrated_planning import kpi as kpi_mod
from sop_integrated_planning.dashboard import build_context
from sop_integrated_planning.models import ScenarioId, jsonable

REPO = Path(__file__).resolve().parent.parent
MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
UPLIFT_SCENARIOS = {ScenarioId.UPSIDE, ScenarioId.CONSTRAINED}


def _provenance(scenario, families, resources, loads, supply_lines, finance_lines):
    """Per (family, month): the full Demand -> Capacity -> Rationing -> Supply ->
    Financials trail for this scenario, sourced from the same objects the engine
    already computed (nothing here is a second calculation of the outcome)."""
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
            uplift_applied = scenario in UPLIFT_SCENARIOS
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


def main() -> int:
    families, resources = cli._load_or_generate_dataset(REPO / "data")
    loads_by, supply_by, finance_by, summary_by = cli.run_all_scenarios(families, resources)
    kpis = kpi_mod.compute_kpis(resources, loads_by, summary_by, finance_by)
    generated_at = datetime.now(timezone.utc).isoformat()

    ctx = build_context(
        families, resources, loads_by, supply_by, finance_by, summary_by, kpis, generated_at
    )

    payload = {
        "generated_at": generated_at,
        "company": ctx["company"],
        "month_names": MONTH_NAMES,
        "resources": ctx["resources"],
        "families": [
            {k: f[k] for k in ("id", "name", "unit_price", "unit_variable_cost", "unit_margin")}
            for f in ctx["families"]
        ],
        "bottleneck": ctx["bottleneck"],
        "scenarios": {},
        "provenance": {},
    }

    for sid, scen in ctx["scenarios"].items():
        # Monthly revenue / margin / lost margin, summed across families.
        by_month: dict[int, dict[str, float]] = defaultdict(
            lambda: {"revenue": 0.0, "gross_margin": 0.0, "lost_revenue": 0.0, "lost_margin": 0.0}
        )
        for fl in finance_by[sid]:
            bucket = by_month[fl.month]
            bucket["revenue"] += fl.revenue
            bucket["gross_margin"] += fl.gross_margin
            bucket["lost_revenue"] += fl.lost_revenue
            bucket["lost_margin"] += fl.lost_margin

        monthly = []
        for row in scen["monthly_totals"]:
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

        payload["scenarios"][sid] = {
            "id": sid,
            "summary": scen["summary"],
            "monthly": monthly,
            "utilization": {
                rid: [
                    {"month": r["month"],
                     "load_hours": r["load_hours"],
                     "available_hours": r["available_hours"],
                     "utilization_pct": r["utilization_pct"]}
                    for r in rows
                ]
                for rid, rows in scen["capacity"]["by_resource"].items()
            },
            "reconciliation": scen["reconciliation"],
        }

        scenario_enum = next(s for s in cli.ALL_SCENARIOS if s.value == sid)
        payload["provenance"][sid] = _provenance(
            scenario_enum, families, resources, loads_by[sid], supply_by[sid], finance_by[sid]
        )

    out = REPO / "mockups" / "data.js"
    out.write_text(
        "/* GENERATED by mockups/build_data.py — do not hand-edit. */\n"
        "window.SOP_DATA = " + json.dumps(payload, indent=2) + ";\n"
    )
    print(f"Wrote {out} ({out.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
