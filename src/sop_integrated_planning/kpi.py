"""
kpi.py — the S&OP / IBP KPI catalog.

Every number here is *computed* from real engine outputs — the resource
loads from `capacity.py`, the supply plans from `constrain.py`, the
financial summaries from `finance.py` — nothing is hardcoded. This is the
layer the CLI's `compare`/`demo` commands and the dashboard both read
from, so the console tables and the HTML tiles are guaranteed to agree.

Catalog (see docs/03-kpi-reference.md for the precise formulas):
- **Fill rate** per scenario: shipped / demanded (the service proxy).
- **Capacity utilization** per resource, peak month, per scenario:
  load / installed capacity (BASE's RCCP denominator, always).
- **Bottleneck resource**: the resource/month with the highest utilization
  in the UPSIDE/CONSTRAINED demand plan (they share one, since RCCP is
  always measured against installed capacity regardless of scenario).
- **Revenue & gross margin** per scenario.
- **Lost revenue / margin at risk**: the value of unmet demand in
  CONSTRAINED — the cost of NOT adding capacity.
- **Upside value unlocked**: Δ gross margin (UPSIDE − CONSTRAINED) — what
  the capacity investment is worth.
- **Inventory value** per scenario (December closing balance, at cost).
"""

from __future__ import annotations

from . import capacity as capacity_mod
from . import finance as finance_mod
from .models import FinanceLine, FinanceSummary, Kpi, Resource, ResourceLoad, ScenarioId, SupplyLine

_MONTH_NAMES = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]


def fill_rate_kpi(scenario: ScenarioId, summary: FinanceSummary) -> Kpi:
    label = f"Fill Rate — {scenario.value.title()}"
    return Kpi(
        key=f"fill_rate_{scenario.value}",
        label=label,
        value=round(summary.fill_rate * 100.0, 2),
        unit="%",
        context="shipped / demanded, full year",
    )


def bottleneck_kpi(resources: list[Resource], loads: list[ResourceLoad]) -> Kpi:
    """
    The single worst (resource, month) combination in the UPSIDE/
    CONSTRAINED demand plan — the resource an exec would ask about first.
    """
    resources_by_id = {r.id: r for r in resources}
    peak = max(loads, key=lambda ld: ld.utilization_pct, default=None)
    if peak is None:
        return Kpi(key="bottleneck", label="Bottleneck Resource", value=0.0, unit="%", context="no data")
    name = resources_by_id[peak.resource_id].name
    month_name = _MONTH_NAMES[peak.month - 1]
    context = f"{name} ({peak.resource_id}) peaks {month_name}"
    if peak.utilization_pct > 100.0:
        context += " — exceeds installed capacity"
    return Kpi(
        key="bottleneck",
        label="Bottleneck Resource Utilization",
        value=peak.utilization_pct,
        unit="%",
        context=context,
    )


def gross_margin_kpi(scenario: ScenarioId, summary: FinanceSummary) -> Kpi:
    return Kpi(
        key=f"gross_margin_{scenario.value}",
        label=f"Gross Margin — {scenario.value.title()}",
        value=summary.total_gross_margin,
        unit="$",
        context="full year, shipped units only",
    )


def revenue_kpi(scenario: ScenarioId, summary: FinanceSummary) -> Kpi:
    return Kpi(
        key=f"revenue_{scenario.value}",
        label=f"Revenue — {scenario.value.title()}",
        value=summary.total_revenue,
        unit="$",
        context="full year, shipped units only",
    )


def lost_margin_kpi(summary: FinanceSummary, finance_lines: list[FinanceLine]) -> Kpi:
    """Margin at risk in CONSTRAINED — the cost of not adding capacity, with the family it concentrates in."""
    by_family = finance_mod.lost_margin_by_family(finance_lines)
    worst_family = max(by_family, key=by_family.get) if by_family else "n/a"
    return Kpi(
        key="lost_margin_constrained",
        label="Margin at Risk (Constrained)",
        value=summary.total_lost_margin,
        unit="$",
        context=f"concentrated in {worst_family}" if by_family.get(worst_family, 0) > 0 else "no shortfall",
    )


def lost_revenue_kpi(summary: FinanceSummary) -> Kpi:
    return Kpi(
        key="lost_revenue_constrained",
        label="Lost Revenue (Constrained)",
        value=summary.total_lost_revenue,
        unit="$",
        context="value of unmet demand, full year",
    )


def upside_value_unlocked_kpi(upside_summary: FinanceSummary, constrained_summary: FinanceSummary) -> Kpi:
    """What the capacity investment is worth: margin captured in UPSIDE that CONSTRAINED leaves on the table."""
    delta = round(upside_summary.total_gross_margin - constrained_summary.total_gross_margin, 2)
    return Kpi(
        key="upside_value_unlocked",
        label="Upside Value Unlocked",
        value=delta,
        unit="$",
        context="Δ gross margin, Upside vs Constrained",
    )


def inventory_value_kpi(scenario: ScenarioId, summary: FinanceSummary) -> Kpi:
    return Kpi(
        key=f"inventory_value_{scenario.value}",
        label=f"Ending Inventory Value — {scenario.value.title()}",
        value=summary.ending_inventory_value,
        unit="$",
        context="December closing balance, at variable cost",
    )


def compute_kpis(
    resources: list[Resource],
    loads_by_scenario: dict[ScenarioId, list[ResourceLoad]],
    summary_by_scenario: dict[ScenarioId, FinanceSummary],
    finance_lines_by_scenario: dict[ScenarioId, list[FinanceLine]],
) -> dict[str, Kpi]:
    """Assemble the full cross-scenario KPI catalog used by the CLI and dashboard."""
    kpis: dict[str, Kpi] = {}

    for scenario in (ScenarioId.BASE, ScenarioId.UPSIDE, ScenarioId.CONSTRAINED):
        summary = summary_by_scenario[scenario]
        kpis[f"fill_rate_{scenario.value}"] = fill_rate_kpi(scenario, summary)
        kpis[f"gross_margin_{scenario.value}"] = gross_margin_kpi(scenario, summary)
        kpis[f"revenue_{scenario.value}"] = revenue_kpi(scenario, summary)
        kpis[f"inventory_value_{scenario.value}"] = inventory_value_kpi(scenario, summary)

    kpis["bottleneck"] = bottleneck_kpi(resources, loads_by_scenario[ScenarioId.UPSIDE])
    kpis["lost_margin_constrained"] = lost_margin_kpi(
        summary_by_scenario[ScenarioId.CONSTRAINED], finance_lines_by_scenario[ScenarioId.CONSTRAINED]
    )
    kpis["lost_revenue_constrained"] = lost_revenue_kpi(summary_by_scenario[ScenarioId.CONSTRAINED])
    kpis["upside_value_unlocked"] = upside_value_unlocked_kpi(
        summary_by_scenario[ScenarioId.UPSIDE], summary_by_scenario[ScenarioId.CONSTRAINED]
    )
    return kpis


def peak_utilization_table(resources: list[Resource], loads: list[ResourceLoad]) -> list[dict]:
    """Per-resource peak utilization row for console/dashboard capacity charts."""
    peaks = capacity_mod.peak_utilization_by_resource(loads)
    rows = []
    for resource in resources:
        rows.append(
            {
                "resource_id": resource.id,
                "resource_name": resource.name,
                "available_hours": resource.monthly_available_hours,
                "peak_utilization_pct": peaks.get(resource.id, 0.0),
            }
        )
    return rows
