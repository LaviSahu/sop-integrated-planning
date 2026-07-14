"""
constrain.py — turns an unconstrained demand plan into a constrained
supply plan: what actually gets produced, shipped, and carried into
next month, once resource hours run out.

This is the "supply planning" + "pre-S&OP reconciliation" heart of the
monthly cycle (Wallace & Stahl): once `capacity.py`'s RCCP shows a
resource is over installed capacity in some month, someone has to decide
what happens next. Two decisions are modeled, one per scenario:

- **UPSIDE ("if we add capacity")**: `effective_capacity_hours` invests
  exactly enough extra hours in an over-loaded resource, in the month(s)
  it's over-loaded, to close the RCCP gap. Nothing is rationed; every
  family gets everything it asked for (subject only to demand itself).
- **CONSTRAINED ("if we don't")**: `effective_capacity_hours` returns the
  resource's installed hours, unchanged. When load exceeds that, hours
  are allocated by **descending unit margin** — the standard "protect the
  highest-margin business first" priority rule — greedily, family by
  family, until the resource's hours run out. A family's actual output
  for the month is capped by the *most* binding resource it touches
  (production needs every resource's hours simultaneously, not just one).

Inventory carries forward month to month: `shipped = min(opening +
produced, demand)` (no backorders — unsold demand this month is a lost
sale, not a promise for next month); `ending_inventory = max(0, opening +
produced - shipped)` becomes next month's opening balance. `fill_rate =
shipped / demand` (1.0 when there was no demand at all).
"""

from __future__ import annotations

from . import capacity as capacity_mod
from .demand import demand_by_family_month
from .models import DemandLine, Family, Resource, ScenarioId, SupplyLine

MONTHS = list(range(1, 13))


def effective_capacity_hours(scenario: ScenarioId, resource: Resource, load_hours: float) -> float:
    """
    Hours actually available to allocate this month, per scenario.

    BASE / CONSTRAINED: installed capacity, unchanged — no investment.
    UPSIDE: installed capacity, topped up to exactly match load whenever
    load would otherwise exceed it — "add just enough capacity to clear
    the gap RCCP flagged," never more, never less.
    """
    if scenario == ScenarioId.UPSIDE:
        return max(resource.monthly_available_hours, load_hours)
    return resource.monthly_available_hours


def _allowed_units_this_month(
    month: int,
    families: list[Family],
    resources: list[Resource],
    demand_by_fm: dict[tuple[str, int], float],
    load_by_rm: dict[tuple[str, int], float],
    scenario: ScenarioId,
) -> dict[tuple[str, str], float]:
    """
    For one month: how many units of each family each resource's hour
    budget can support, in isolation. Unconstrained resources grant every
    user its full demand-implied units; constrained resources ration by
    descending unit margin. A family's actual production (computed by the
    caller) is the MIN of this across every resource it touches, so no
    resource ever ends up over-committed once the mins are taken.
    """
    allowed: dict[tuple[str, str], float] = {}
    for resource in resources:
        users = [f for f in families if f.resource_hours_per_unit.get(resource.id, 0.0) > 0.0]
        if not users:
            continue
        load_hours = load_by_rm.get((resource.id, month), 0.0)
        capacity_hours = effective_capacity_hours(scenario, resource, load_hours)

        if load_hours <= capacity_hours + 1e-9:
            # Unconstrained: everyone gets exactly what they asked for.
            for family in users:
                allowed[(family.id, resource.id)] = demand_by_fm.get((family.id, month), 0.0)
            continue

        # Constrained: ration by descending unit margin (protect the
        # highest-margin business first — the priority rule).
        remaining_hours = capacity_hours
        for family in sorted(users, key=lambda f: f.unit_margin, reverse=True):
            hours_per_unit = family.resource_hours_per_unit[resource.id]
            demand_units = demand_by_fm.get((family.id, month), 0.0)
            wanted_hours = demand_units * hours_per_unit
            granted_hours = max(0.0, min(wanted_hours, remaining_hours))
            allowed[(family.id, resource.id)] = granted_hours / hours_per_unit if hours_per_unit > 0 else demand_units
            remaining_hours = max(0.0, remaining_hours - granted_hours)
    return allowed


def build_supply_plan(
    demand_lines: list[DemandLine],
    families: list[Family],
    resources: list[Resource],
    scenario: ScenarioId,
) -> list[SupplyLine]:
    """The full 12-month constrained supply plan for every family."""
    demand_by_fm = demand_by_family_month(demand_lines)
    loads = capacity_mod.compute_loads(demand_lines, families, resources)
    load_by_rm = capacity_mod.load_hours_by_resource_month(loads)

    opening: dict[str, float] = {f.id: f.opening_inventory_units for f in families}
    lines: list[SupplyLine] = []

    for month in MONTHS:
        allowed = _allowed_units_this_month(month, families, resources, demand_by_fm, load_by_rm, scenario)

        for family in families:
            demand_units = demand_by_fm.get((family.id, month), 0.0)
            resource_ids_used = [rid for rid, hpu in family.resource_hours_per_unit.items() if hpu > 0.0]
            if resource_ids_used:
                produced = min(allowed[(family.id, rid)] for rid in resource_ids_used)
            else:
                produced = demand_units
            # No build-ahead in this single-stage model: never produce
            # more than the month's own demand.
            produced = max(0.0, min(produced, demand_units))

            opening_units = opening[family.id]
            shipped = min(opening_units + produced, demand_units)
            unmet = max(0.0, demand_units - shipped)
            ending = max(0.0, opening_units + produced - shipped)
            fill_rate = (shipped / demand_units) if demand_units > 0 else 1.0

            lines.append(
                SupplyLine(
                    scenario=scenario,
                    family_id=family.id,
                    month=month,
                    demand_units=round(demand_units, 2),
                    produced_units=round(produced, 2),
                    opening_inventory_units=round(opening_units, 2),
                    shipped_units=round(shipped, 2),
                    unmet_units=round(unmet, 2),
                    ending_inventory_units=round(ending, 2),
                    fill_rate=round(fill_rate, 4),
                )
            )
            opening[family.id] = ending

    return lines


def overall_fill_rate(supply_lines: list[SupplyLine]) -> float:
    """Aggregate fill rate across every family/month: total shipped / total demand."""
    total_demand = sum(sl.demand_units for sl in supply_lines)
    total_shipped = sum(sl.shipped_units for sl in supply_lines)
    return round(total_shipped / total_demand, 4) if total_demand > 0 else 1.0
