"""
capacity.py — Rough-Cut Capacity Planning (RCCP).

RCCP is standard MRP-II / APICS body-of-knowledge practice: before
committing a demand plan, load it against the key shared resources it
would consume and check whether the *installed* capacity can physically
support it — a feasibility test, not a detailed finite schedule (that's
what full Capacity Requirements Planning / detailed scheduling is for,
downstream of S&OP).

The load/utilization computed here is ALWAYS measured against each
resource's installed (base) monthly hours — `Resource.monthly_available_hours`
— regardless of scenario. That is deliberate: RCCP's job is to tell you
what you can build with what you *have today*. Whether you then decide to
invest in more capacity (the UPSIDE scenario's "if we add capacity") or
ration what you have (the CONSTRAINED scenario's "if we don't") is a
downstream decision made in `constrain.py`, not a fact this module gets to
change. That is also why the BASE and the UPSIDE/CONSTRAINED demand plans
can show very different utilization here even though only `constrain.py`
ultimately decides what gets produced.
"""

from __future__ import annotations

from .models import DemandLine, Family, Resource, ResourceLoad, ScenarioId

MONTHS = list(range(1, 13))


def resource_ids_for_family(family: Family) -> list[str]:
    return list(family.resource_hours_per_unit.keys())


def compute_loads(
    demand_lines: list[DemandLine],
    families: list[Family],
    resources: list[Resource],
) -> list[ResourceLoad]:
    """
    RCCP load per resource/month: sum over families of
    demand_units x hours_per_unit for that resource. Utilization is
    load / installed available hours; `is_bottleneck` flags > 100%.
    """
    families_by_id = {f.id: f for f in families}
    scenario = demand_lines[0].scenario if demand_lines else ScenarioId.BASE
    demand_by_fm: dict[tuple[str, int], float] = {(d.family_id, d.month): d.demand_units for d in demand_lines}

    loads: list[ResourceLoad] = []
    for resource in resources:
        for month in MONTHS:
            load_hours = 0.0
            for family in families:
                hours_per_unit = family.resource_hours_per_unit.get(resource.id, 0.0)
                if hours_per_unit <= 0.0:
                    continue
                demand = demand_by_fm.get((family.id, month), 0.0)
                load_hours += demand * hours_per_unit
            load_hours = round(load_hours, 2)
            utilization = (load_hours / resource.monthly_available_hours * 100.0) if resource.monthly_available_hours else 0.0
            loads.append(
                ResourceLoad(
                    scenario=scenario,
                    resource_id=resource.id,
                    month=month,
                    load_hours=load_hours,
                    available_hours=resource.monthly_available_hours,
                    utilization_pct=round(utilization, 2),
                    is_bottleneck=utilization > 100.0,
                )
            )
    del families_by_id
    return loads


def bottlenecks(loads: list[ResourceLoad]) -> list[ResourceLoad]:
    """Every (resource, month) where installed capacity is exceeded."""
    return [ld for ld in loads if ld.is_bottleneck]


def peak_utilization_by_resource(loads: list[ResourceLoad]) -> dict[str, float]:
    """The single worst (highest) monthly utilization per resource, across the year."""
    peaks: dict[str, float] = {}
    for ld in loads:
        peaks[ld.resource_id] = max(peaks.get(ld.resource_id, 0.0), ld.utilization_pct)
    return peaks


def binding_resource(loads: list[ResourceLoad]) -> str | None:
    """
    The single most over-loaded resource across the year (highest peak
    utilization) — "the binding resource" an exec would ask about first.
    Returns None if nothing exceeds 100%.
    """
    peaks = peak_utilization_by_resource(loads)
    over = {rid: pct for rid, pct in peaks.items() if pct > 100.0}
    if not over:
        return None
    return max(over, key=over.get)


def load_hours_by_resource_month(loads: list[ResourceLoad]) -> dict[tuple[str, int], float]:
    return {(ld.resource_id, ld.month): ld.load_hours for ld in loads}
