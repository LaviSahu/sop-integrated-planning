"""
models.py — the shared vocabulary of the S&OP / IBP cockpit.

The whole point of Sales & Operations Planning is that sales, operations,
and finance stop arguing from three different spreadsheets and agree on
one plan, expressed in one shared vocabulary (Wallace & Stahl's *Sales
and Operations Planning: The How-To Handbook*, and the IBP extension of
that reconciliation described by Oliver Wight's *Transition from Sales
and Operations Planning to Integrated Business Planning*, 2nd ed. 2022,
and Palmatier & Crum's *Enterprise Sales and Operations Planning*). This
module is that shared vocabulary, expressed as typed dataclasses instead
of prose:

- Company primitives: `Family`, `Resource` — the product families Cascade
  Appliances sells and the shared production resources they compete for.
- Demand primitives: `DemandLine` — one family's demand for one month
  under one scenario, the output of `demand.py`.
- Capacity primitives: `ResourceLoad` — one resource's Rough-Cut Capacity
  Planning (RCCP) load/utilization for one month, the output of
  `capacity.py`.
- Supply primitives: `SupplyLine` — one family's constrained monthly
  supply plan (produced, shipped, unmet, ending inventory), the output of
  `constrain.py`.
- Finance primitives: `FinanceLine`, `FinanceSummary` — the per-month and
  rolled-up P&L-style reconciliation, the output of `finance.py`.
- KPI primitive: `Kpi` — a single labeled, computed number for the
  console/dashboard, the output of `kpi.py`.

Everything here is a plain `@dataclass`: no behavior, no globals, just
shape. Behavior lives in the modules named after the verbs (generate,
plan, load, constrain, reconcile, score).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum


# --------------------------------------------------------------------------
# Enumerations — the controlled vocabularies used across the engine.
# --------------------------------------------------------------------------


class ScenarioId(str, Enum):
    """
    The three scenarios the cockpit reconciles side by side.

    BASE: base demand against installed (base) capacity — feasible by
    construction, the "we already agreed to this" plan.
    UPSIDE: base + upside demand overlay, WITH the capacity gap closed
    (the business decides to invest just enough to capture it) — "if we
    add capacity."
    CONSTRAINED: the same upside demand, but capacity held at base
    availability (no investment) — "if we don't." `constrain.py` has to
    ration scarce hours by margin priority, and the shortfall is real.
    """

    BASE = "base"
    UPSIDE = "upside"
    CONSTRAINED = "constrained"


SCENARIO_LABELS: dict[ScenarioId, str] = {
    ScenarioId.BASE: "Base",
    ScenarioId.UPSIDE: "Upside (capacity added)",
    ScenarioId.CONSTRAINED: "Constrained (no capacity added)",
}


# --------------------------------------------------------------------------
# Company primitives
# --------------------------------------------------------------------------


@dataclass
class Family:
    """
    A product family Cascade Appliances plans and sells (e.g. Refrigerators).

    `base_monthly_demand` is 12 unconstrained demand figures (units),
    already seasonality-shaped by `datagen.py`. `upside_uplift_pct` is
    the promotion/market-growth overlay applied on top of base demand for
    the UPSIDE and CONSTRAINED scenarios (0.0 for families with no upside
    play). `resource_hours_per_unit` maps resource id -> hours consumed
    per unit produced; a family that doesn't touch a resource simply
    omits it (treated as 0.0 everywhere else in the engine).
    """

    id: str
    name: str
    unit_price: float
    unit_variable_cost: float
    opening_inventory_units: float
    base_monthly_demand: list[float]
    upside_uplift_pct: float
    resource_hours_per_unit: dict[str, float] = field(default_factory=dict)

    @property
    def unit_margin(self) -> float:
        return round(self.unit_price - self.unit_variable_cost, 4)


@dataclass
class Resource:
    """
    A shared production resource (e.g. Assembly Line A) with a fixed
    monthly hour budget. `monthly_available_hours` is the *installed*
    (base) capacity — the number every RCCP utilization figure is
    measured against, scenario or no scenario, because installed
    capacity doesn't change just because someone hopes demand will be
    higher; only a real investment decision changes it (see
    `constrain.effective_capacity_hours`).
    """

    id: str
    name: str
    monthly_available_hours: float


# --------------------------------------------------------------------------
# Demand primitives
# --------------------------------------------------------------------------


@dataclass
class DemandLine:
    """One family's unconstrained demand for one month under one scenario."""

    scenario: ScenarioId
    family_id: str
    month: int  # 1-12
    demand_units: float


# --------------------------------------------------------------------------
# Capacity primitives (RCCP)
# --------------------------------------------------------------------------


@dataclass
class ResourceLoad:
    """
    One resource's Rough-Cut Capacity Planning result for one month under
    one scenario: how many hours the demand plan asks for, how many are
    installed, and the resulting utilization. `is_bottleneck` flags
    utilization strictly over 100% — the RCCP feasibility test.
    """

    scenario: ScenarioId
    resource_id: str
    month: int
    load_hours: float
    available_hours: float
    utilization_pct: float
    is_bottleneck: bool


# --------------------------------------------------------------------------
# Supply primitives
# --------------------------------------------------------------------------


@dataclass
class SupplyLine:
    """
    One family's constrained monthly supply outcome: how much was
    produced (after any margin-priority rationing), how much shipped
    (from opening inventory + production, capped at demand), the
    resulting fill rate and unmet demand, and the ending inventory
    carried into next month.
    """

    scenario: ScenarioId
    family_id: str
    month: int
    demand_units: float
    produced_units: float
    opening_inventory_units: float
    shipped_units: float
    unmet_units: float
    ending_inventory_units: float
    fill_rate: float


# --------------------------------------------------------------------------
# Finance primitives
# --------------------------------------------------------------------------


@dataclass
class FinanceLine:
    """One family's monthly financial reconciliation under one scenario."""

    scenario: ScenarioId
    family_id: str
    month: int
    revenue: float
    gross_margin: float
    lost_revenue: float
    lost_margin: float
    inventory_value: float


@dataclass
class FinanceSummary:
    """
    The one-page P&L-style roll-up for a scenario: totals across every
    family and month, ready for the exec KPI tiles and the reconciliation
    table.
    """

    scenario: ScenarioId
    total_revenue: float
    total_gross_margin: float
    total_lost_revenue: float
    total_lost_margin: float
    ending_inventory_value: float
    fill_rate: float


# --------------------------------------------------------------------------
# KPI primitive
# --------------------------------------------------------------------------


@dataclass
class Kpi:
    key: str
    label: str
    value: float
    unit: str
    context: str = ""


# --------------------------------------------------------------------------
# JSON helper — shared by every module and dashboard.py so output/*.json
# and the dashboard's embedded <script> DATA blob use one consistent,
# dependency-free serialization convention.
# --------------------------------------------------------------------------


def jsonable(obj):
    """
    Recursively convert dataclasses / Enums / dates / dicts / lists into
    plain JSON-serializable structures. Used instead of a library like
    `pydantic` to keep the project stdlib-only.
    """
    from dataclasses import fields, is_dataclass

    if is_dataclass(obj) and not isinstance(obj, type):
        result = {f.name: jsonable(getattr(obj, f.name)) for f in fields(obj)}
        if isinstance(obj, Family):
            result["unit_margin"] = obj.unit_margin
        return result
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, date):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [jsonable(v) for v in obj]
    return obj
