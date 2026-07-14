"""Tests for demand.py — the unconstrained demand plan."""

import unittest

import _bootstrap  # noqa: F401

from fixtures import toy_families_and_resources

from sop_integrated_planning.demand import (
    build_demand_plan,
    demand_by_family_month,
    monthly_demand,
    total_annual_demand,
)
from sop_integrated_planning.models import ScenarioId


class TestMonthlyDemand(unittest.TestCase):
    def setUp(self) -> None:
        self.families, _ = toy_families_and_resources()
        self.fam1 = self.families[0]

    def test_base_scenario_is_unmodified(self) -> None:
        self.assertEqual(monthly_demand(self.fam1, 1, ScenarioId.BASE), 10.0)

    def test_upside_applies_uplift(self) -> None:
        # upside_uplift_pct = 1.0 -> demand doubles
        self.assertEqual(monthly_demand(self.fam1, 1, ScenarioId.UPSIDE), 20.0)

    def test_constrained_shares_upside_demand(self) -> None:
        self.assertEqual(
            monthly_demand(self.fam1, 1, ScenarioId.CONSTRAINED),
            monthly_demand(self.fam1, 1, ScenarioId.UPSIDE),
        )

    def test_zero_uplift_family_unchanged_in_upside(self) -> None:
        flat = self.families[1].__class__(
            **{**self.families[1].__dict__, "upside_uplift_pct": 0.0}
        )
        self.assertEqual(monthly_demand(flat, 1, ScenarioId.UPSIDE), flat.base_monthly_demand[0])


class TestBuildDemandPlan(unittest.TestCase):
    def test_plan_has_one_line_per_family_per_month(self) -> None:
        families, _ = toy_families_and_resources()
        lines = build_demand_plan(families, ScenarioId.BASE)
        self.assertEqual(len(lines), len(families) * 12)

    def test_all_lines_tagged_with_scenario(self) -> None:
        families, _ = toy_families_and_resources()
        lines = build_demand_plan(families, ScenarioId.UPSIDE)
        self.assertTrue(all(line.scenario == ScenarioId.UPSIDE for line in lines))


class TestDemandByFamilyMonth(unittest.TestCase):
    def test_index_lookup_matches_source_line(self) -> None:
        families, _ = toy_families_and_resources()
        lines = build_demand_plan(families, ScenarioId.BASE)
        index = demand_by_family_month(lines)
        self.assertEqual(index[("FAM-1", 1)], 10.0)
        self.assertEqual(len(index), len(families) * 12)


class TestTotalAnnualDemand(unittest.TestCase):
    def test_sums_twelve_months(self) -> None:
        families, _ = toy_families_and_resources()
        lines = build_demand_plan(families, ScenarioId.BASE)
        totals = total_annual_demand(lines)
        self.assertEqual(totals["FAM-1"], 120.0)
        self.assertEqual(totals["FAM-2"], 120.0)


if __name__ == "__main__":
    unittest.main()
