"""Tests for capacity.py — Rough-Cut Capacity Planning (RCCP)."""

import unittest

import _bootstrap  # noqa: F401

from fixtures import toy_families_and_resources

from sop_integrated_planning.capacity import (
    binding_resource,
    bottlenecks,
    compute_loads,
    load_hours_by_resource_month,
    peak_utilization_by_resource,
)
from sop_integrated_planning.demand import build_demand_plan
from sop_integrated_planning.models import ScenarioId


class TestComputeLoadsBase(unittest.TestCase):
    def setUp(self) -> None:
        self.families, self.resources = toy_families_and_resources()
        demand_lines = build_demand_plan(self.families, ScenarioId.BASE)
        self.loads = compute_loads(demand_lines, self.families, self.resources)

    def test_load_hours_hand_computed(self) -> None:
        # (10 + 10) units x 5 hrs/unit = 100 hrs, every month.
        jan = next(ld for ld in self.loads if ld.month == 1)
        self.assertEqual(jan.load_hours, 100.0)

    def test_utilization_at_exactly_100_is_not_a_bottleneck(self) -> None:
        jan = next(ld for ld in self.loads if ld.month == 1)
        self.assertEqual(jan.utilization_pct, 100.0)
        self.assertFalse(jan.is_bottleneck)  # strictly > 100 required

    def test_one_resource_yields_twelve_loads(self) -> None:
        self.assertEqual(len(self.loads), 12)


class TestComputeLoadsUpside(unittest.TestCase):
    def setUp(self) -> None:
        self.families, self.resources = toy_families_and_resources()
        demand_lines = build_demand_plan(self.families, ScenarioId.UPSIDE)
        self.loads = compute_loads(demand_lines, self.families, self.resources)

    def test_load_doubles_and_exceeds_capacity(self) -> None:
        # (20 + 20) units x 5 hrs/unit = 200 hrs vs 100 installed = 200%.
        jan = next(ld for ld in self.loads if ld.month == 1)
        self.assertEqual(jan.load_hours, 200.0)
        self.assertEqual(jan.utilization_pct, 200.0)
        self.assertTrue(jan.is_bottleneck)

    def test_bottlenecks_returns_only_over_capacity_entries(self) -> None:
        over = bottlenecks(self.loads)
        self.assertEqual(len(over), 12)
        self.assertTrue(all(ld.utilization_pct > 100.0 for ld in over))


class TestPeakAndBindingResource(unittest.TestCase):
    def test_peak_utilization_matches_flat_monthly_value(self) -> None:
        families, resources = toy_families_and_resources()
        demand_lines = build_demand_plan(families, ScenarioId.UPSIDE)
        loads = compute_loads(demand_lines, families, resources)
        peaks = peak_utilization_by_resource(loads)
        self.assertEqual(peaks["RES-A"], 200.0)

    def test_binding_resource_none_when_nothing_over_capacity(self) -> None:
        families, resources = toy_families_and_resources()
        demand_lines = build_demand_plan(families, ScenarioId.BASE)
        loads = compute_loads(demand_lines, families, resources)
        self.assertIsNone(binding_resource(loads))

    def test_binding_resource_identifies_the_bottleneck(self) -> None:
        families, resources = toy_families_and_resources()
        demand_lines = build_demand_plan(families, ScenarioId.UPSIDE)
        loads = compute_loads(demand_lines, families, resources)
        self.assertEqual(binding_resource(loads), "RES-A")


class TestLoadHoursByResourceMonth(unittest.TestCase):
    def test_index_matches_source_loads(self) -> None:
        families, resources = toy_families_and_resources()
        demand_lines = build_demand_plan(families, ScenarioId.BASE)
        loads = compute_loads(demand_lines, families, resources)
        index = load_hours_by_resource_month(loads)
        self.assertEqual(index[("RES-A", 1)], 100.0)


if __name__ == "__main__":
    unittest.main()
