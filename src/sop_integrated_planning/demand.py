"""
demand.py — builds the unconstrained demand plan per family/month/scenario.

This is stage one of the monthly S&OP cycle (Wallace & Stahl's "demand
planning" step): before anyone checks whether it can be built, sold, or
paid for, someone has to state what demand looks like. Here that's
deliberately trivial arithmetic — base demand, optionally uplifted — so
that every later module (capacity, constrain, finance) can be reasoned
about independently of how demand was produced.

`ScenarioId.UPSIDE` and `ScenarioId.CONSTRAINED` share the exact same
demand plan (the promotion/market-growth case) — see models.py's
`ScenarioId` docstring for why they diverge later, in `constrain.py`, not
here. `ScenarioId.BASE` never applies the uplift.
"""

from __future__ import annotations

from .models import DemandLine, Family, ScenarioId

MONTHS = list(range(1, 13))

# Scenarios that apply each family's upside_uplift_pct on top of base demand.
UPLIFT_SCENARIOS = {ScenarioId.UPSIDE, ScenarioId.CONSTRAINED}


def monthly_demand(family: Family, month: int, scenario: ScenarioId) -> float:
    """Demand for one family/month/scenario: base, optionally uplifted."""
    base = family.base_monthly_demand[month - 1]
    if scenario in UPLIFT_SCENARIOS:
        return round(base * (1.0 + family.upside_uplift_pct), 2)
    return base


def build_demand_plan(families: list[Family], scenario: ScenarioId) -> list[DemandLine]:
    """The full 12-month demand plan for every family under one scenario."""
    lines: list[DemandLine] = []
    for family in families:
        for month in MONTHS:
            lines.append(
                DemandLine(
                    scenario=scenario,
                    family_id=family.id,
                    month=month,
                    demand_units=monthly_demand(family, month, scenario),
                )
            )
    return lines


def demand_by_family_month(lines: list[DemandLine]) -> dict[tuple[str, int], float]:
    """Index a demand plan for O(1) lookup by (family_id, month)."""
    return {(line.family_id, line.month): line.demand_units for line in lines}


def total_annual_demand(lines: list[DemandLine]) -> dict[str, float]:
    """Sum of demand_units across all 12 months, per family."""
    totals: dict[str, float] = {}
    for line in lines:
        totals[line.family_id] = totals.get(line.family_id, 0.0) + line.demand_units
    return {k: round(v, 2) for k, v in totals.items()}
