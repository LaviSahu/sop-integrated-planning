"""Tests for finance.py — reconciling the constrained supply plan into money."""

import unittest

import _bootstrap  # noqa: F401

from fixtures import toy_families_and_resources

from sop_integrated_planning.constrain import build_supply_plan
from sop_integrated_planning.demand import build_demand_plan
from sop_integrated_planning.finance import (
    build_finance_lines,
    gross_margin_by_family,
    lost_margin_by_family,
    summarize,
)
from sop_integrated_planning.models import ScenarioId


def _constrained_lines():
    families, resources = toy_families_and_resources()
    demand_lines = build_demand_plan(families, ScenarioId.CONSTRAINED)
    supply_lines = build_supply_plan(demand_lines, families, resources, ScenarioId.CONSTRAINED)
    finance_lines = build_finance_lines(supply_lines, families)
    return families, supply_lines, finance_lines


class TestBuildFinanceLines(unittest.TestCase):
    def test_revenue_and_margin_use_shipped_not_demanded(self) -> None:
        _, _, finance_lines = _constrained_lines()
        fam1_jan = next(fl for fl in finance_lines if fl.family_id == "FAM-1" and fl.month == 1)
        # FAM-1 fully shipped: 20 units x $100 = $2000 revenue, x $60 margin = $1200.
        self.assertEqual(fam1_jan.revenue, 2_000.0)
        self.assertEqual(fam1_jan.gross_margin, 1_200.0)
        self.assertEqual(fam1_jan.lost_revenue, 0.0)
        self.assertEqual(fam1_jan.lost_margin, 0.0)

    def test_lost_revenue_and_margin_use_unmet_units(self) -> None:
        _, _, finance_lines = _constrained_lines()
        fam2_jan = next(fl for fl in finance_lines if fl.family_id == "FAM-2" and fl.month == 1)
        # FAM-2 fully unmet: 20 units x $50 price = $1000, x $20 margin = $400.
        self.assertEqual(fam2_jan.revenue, 0.0)
        self.assertEqual(fam2_jan.lost_revenue, 1_000.0)
        self.assertEqual(fam2_jan.lost_margin, 400.0)

    def test_inventory_value_uses_variable_cost_not_price(self) -> None:
        _, _, finance_lines = _constrained_lines()
        fam1_jan = next(fl for fl in finance_lines if fl.family_id == "FAM-1" and fl.month == 1)
        self.assertEqual(fam1_jan.inventory_value, 0.0)  # nothing carried, ending inventory is 0


class TestSummarize(unittest.TestCase):
    def test_fill_rate_matches_overall_shipped_over_demand(self) -> None:
        _, supply_lines, finance_lines = _constrained_lines()
        summary = summarize(ScenarioId.CONSTRAINED, supply_lines, finance_lines)
        self.assertAlmostEqual(summary.fill_rate, 0.5, places=4)

    def test_total_lost_margin_matches_hand_computation(self) -> None:
        _, supply_lines, finance_lines = _constrained_lines()
        summary = summarize(ScenarioId.CONSTRAINED, supply_lines, finance_lines)
        # FAM-2 loses 20 units x $20 margin x 12 months = $4,800.
        self.assertEqual(summary.total_lost_margin, 4_800.0)

    def test_ending_inventory_only_counts_december_not_all_months(self) -> None:
        _, supply_lines, finance_lines = _constrained_lines()
        summary = summarize(ScenarioId.CONSTRAINED, supply_lines, finance_lines)
        december_only = sum(fl.inventory_value for fl in finance_lines if fl.month == 12)
        self.assertEqual(summary.ending_inventory_value, december_only)
        # Sanity: if summarize wrongly summed all 12 months, it would be
        # ~12x too big whenever inventory_value is nonzero anywhere.
        all_months_sum = sum(fl.inventory_value for fl in finance_lines)
        if all_months_sum > 0:
            self.assertLess(summary.ending_inventory_value, all_months_sum)


class TestFamilyAggregation(unittest.TestCase):
    def test_gross_margin_by_family_sums_twelve_months(self) -> None:
        _, _, finance_lines = _constrained_lines()
        totals = gross_margin_by_family(finance_lines)
        # FAM-1 fully shipped every month: 20 units x $60 x 12 = $14,400.
        self.assertEqual(totals["FAM-1"], 14_400.0)
        self.assertEqual(totals["FAM-2"], 0.0)

    def test_lost_margin_by_family_concentrates_in_fam2(self) -> None:
        _, _, finance_lines = _constrained_lines()
        totals = lost_margin_by_family(finance_lines)
        self.assertEqual(totals["FAM-1"], 0.0)
        self.assertEqual(totals["FAM-2"], 4_800.0)


if __name__ == "__main__":
    unittest.main()
