"""Tests for constrain.py — the constrained supply plan and margin-priority rationing."""

import unittest

import _bootstrap  # noqa: F401

from fixtures import toy_families_and_resources, toy_family_with_opening_inventory

from sop_integrated_planning.constrain import (
    build_supply_plan,
    effective_capacity_hours,
    overall_fill_rate,
)
from sop_integrated_planning.models import Resource, ScenarioId


class TestEffectiveCapacityHours(unittest.TestCase):
    def setUp(self) -> None:
        self.resource = Resource(id="RES-A", name="A", monthly_available_hours=100.0)

    def test_base_ignores_load(self) -> None:
        self.assertEqual(effective_capacity_hours(ScenarioId.BASE, self.resource, 999.0), 100.0)

    def test_constrained_ignores_load_no_investment(self) -> None:
        self.assertEqual(effective_capacity_hours(ScenarioId.CONSTRAINED, self.resource, 999.0), 100.0)

    def test_upside_tops_up_to_exactly_close_the_gap(self) -> None:
        self.assertEqual(effective_capacity_hours(ScenarioId.UPSIDE, self.resource, 250.0), 250.0)

    def test_upside_never_goes_below_installed(self) -> None:
        self.assertEqual(effective_capacity_hours(ScenarioId.UPSIDE, self.resource, 50.0), 100.0)


class TestBuildSupplyPlanBase(unittest.TestCase):
    def test_both_families_fully_supplied_at_exactly_100_pct_load(self) -> None:
        from sop_integrated_planning.demand import build_demand_plan

        families, resources = toy_families_and_resources()
        demand_lines = build_demand_plan(families, ScenarioId.BASE)
        lines = build_supply_plan(demand_lines, families, resources, ScenarioId.BASE)
        for line in lines:
            self.assertEqual(line.shipped_units, line.demand_units)
            self.assertEqual(line.unmet_units, 0.0)
            self.assertEqual(line.fill_rate, 1.0)


class TestBuildSupplyPlanUpside(unittest.TestCase):
    def test_both_families_fully_supplied_after_capacity_investment(self) -> None:
        from sop_integrated_planning.demand import build_demand_plan

        families, resources = toy_families_and_resources()
        demand_lines = build_demand_plan(families, ScenarioId.UPSIDE)
        lines = build_supply_plan(demand_lines, families, resources, ScenarioId.UPSIDE)
        for line in lines:
            self.assertEqual(line.demand_units, 20.0)
            self.assertEqual(line.shipped_units, 20.0)
            self.assertEqual(line.unmet_units, 0.0)


class TestBuildSupplyPlanConstrained(unittest.TestCase):
    def setUp(self) -> None:
        from sop_integrated_planning.demand import build_demand_plan

        self.families, self.resources = toy_families_and_resources()
        demand_lines = build_demand_plan(self.families, ScenarioId.CONSTRAINED)
        self.lines = build_supply_plan(demand_lines, self.families, self.resources, ScenarioId.CONSTRAINED)

    def test_higher_margin_family_fully_protected(self) -> None:
        fam1_lines = [ln for ln in self.lines if ln.family_id == "FAM-1"]
        self.assertTrue(all(ln.shipped_units == 20.0 for ln in fam1_lines))
        self.assertTrue(all(ln.unmet_units == 0.0 for ln in fam1_lines))
        self.assertTrue(all(ln.fill_rate == 1.0 for ln in fam1_lines))

    def test_lower_margin_family_absorbs_the_entire_shortfall(self) -> None:
        fam2_lines = [ln for ln in self.lines if ln.family_id == "FAM-2"]
        self.assertTrue(all(ln.produced_units == 0.0 for ln in fam2_lines))
        self.assertTrue(all(ln.shipped_units == 0.0 for ln in fam2_lines))
        self.assertTrue(all(ln.unmet_units == 20.0 for ln in fam2_lines))
        self.assertTrue(all(ln.fill_rate == 0.0 for ln in fam2_lines))

    def test_overall_fill_rate_is_exactly_one_half(self) -> None:
        # FAM-1 fully shipped (20/mo), FAM-2 fully unmet (0/mo shipped of 20 demanded)
        # -> total shipped = total demand / 2.
        self.assertAlmostEqual(overall_fill_rate(self.lines), 0.5, places=4)


class TestOpeningInventoryCarryover(unittest.TestCase):
    def test_ending_inventory_stays_flat_since_no_build_ahead(self) -> None:
        from sop_integrated_planning.demand import build_demand_plan

        families, resources = toy_family_with_opening_inventory()
        demand_lines = build_demand_plan(families, ScenarioId.BASE)
        lines = build_supply_plan(demand_lines, families, resources, ScenarioId.BASE)

        january = lines[0]
        self.assertEqual(january.opening_inventory_units, 5.0)
        self.assertEqual(january.produced_units, 10.0)  # capped at demand, never build-ahead
        self.assertEqual(january.shipped_units, 10.0)  # min(5+10, 10)
        self.assertEqual(january.ending_inventory_units, 5.0)  # 5 + 10 - 10

        december = lines[-1]
        self.assertEqual(december.opening_inventory_units, 5.0)
        self.assertEqual(december.ending_inventory_units, 5.0)


if __name__ == "__main__":
    unittest.main()
