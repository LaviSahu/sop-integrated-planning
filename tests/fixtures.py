"""
fixtures.py — small, hand-computable toy families/resources shared
across the test suite. Not a test module itself (no `Test*` classes),
so `unittest discover` skips it as a test-case source while remaining
importable by the modules that need it.

`toy_families_and_resources()` is deliberately tuned so every number in
`capacity.py` / `constrain.py` / `finance.py` can be hand-checked:

- One resource, RES-A, 100 installed hours/month.
- Two families, each demanding 10 units/month at base, each consuming
  5 hours/unit on RES-A:
    BASE load = (10 + 10) x 5 = 100 hours == 100% of RES-A exactly (a
    boundary case: at, not over, capacity -> NOT a bottleneck, and NOT
    rationed, since `constrain.py`'s test is `load_hours <= capacity`).
- Both families carry `upside_uplift_pct = 1.0` (demand doubles under
  UPSIDE/CONSTRAINED): load becomes (20 + 20) x 5 = 200 hours == 200%
  of RES-A -> a clean, hand-computable bottleneck.
- FAM-1's unit margin (60) is strictly higher than FAM-2's (20), so the
  margin-priority rationing in CONSTRAINED has an unambiguous, hand-
  computable answer: FAM-1 is fully protected (its 20 units x 5 hours =
  100 hours exactly exhausts RES-A) and FAM-2 gets zero hours, zero
  units, 100% unmet, every month.

`toy_family_with_opening_inventory()` isolates the inventory-carryover
arithmetic in `constrain.py` from any capacity constraint at all.
"""

from __future__ import annotations

from sop_integrated_planning.models import Family, Resource


def toy_families_and_resources() -> tuple[list[Family], list[Resource]]:
    resources = [Resource(id="RES-A", name="Resource A", monthly_available_hours=100.0)]
    families = [
        Family(
            id="FAM-1",
            name="Widget",
            unit_price=100.0,
            unit_variable_cost=40.0,  # unit_margin = 60.0
            opening_inventory_units=0.0,
            base_monthly_demand=[10.0] * 12,
            upside_uplift_pct=1.0,  # doubles demand under UPSIDE/CONSTRAINED
            resource_hours_per_unit={"RES-A": 5.0},
        ),
        Family(
            id="FAM-2",
            name="Gadget",
            unit_price=50.0,
            unit_variable_cost=30.0,  # unit_margin = 20.0 (lower priority than FAM-1)
            opening_inventory_units=0.0,
            base_monthly_demand=[10.0] * 12,
            upside_uplift_pct=1.0,
            resource_hours_per_unit={"RES-A": 5.0},
        ),
    ]
    return families, resources


def toy_family_with_opening_inventory() -> tuple[list[Family], list[Resource]]:
    """
    One family, ample capacity, opening inventory of 5 units against a
    flat demand of 10 units/month. Since production always refills to
    exactly that month's demand (this engine never builds ahead), the
    5-unit opening cushion is never drawn down or grown: shipped is
    capped at demand (10), so ending inventory stays flat at 5 forever.
    A deliberately simple, hand-checkable steady state.
    """
    resources = [Resource(id="RES-A", name="Resource A", monthly_available_hours=1_000.0)]
    families = [
        Family(
            id="FAM-1",
            name="Widget",
            unit_price=100.0,
            unit_variable_cost=40.0,
            opening_inventory_units=5.0,
            base_monthly_demand=[10.0] * 12,
            upside_uplift_pct=0.0,
            resource_hours_per_unit={"RES-A": 1.0},
        ),
    ]
    return families, resources
