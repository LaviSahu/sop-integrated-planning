"""Tests for kpi.py — the cross-scenario KPI catalog."""

import unittest

import _bootstrap  # noqa: F401

from fixtures import toy_families_and_resources

from sop_integrated_planning.capacity import compute_loads
from sop_integrated_planning.constrain import build_supply_plan
from sop_integrated_planning.demand import build_demand_plan
from sop_integrated_planning.finance import build_finance_lines, summarize
from sop_integrated_planning.kpi import (
    bottleneck_kpi,
    compute_kpis,
    fill_rate_kpi,
    lost_margin_kpi,
    peak_utilization_table,
    upside_value_unlocked_kpi,
)
from sop_integrated_planning.models import ScenarioId


def _run(scenario, families, resources):
    demand_lines = build_demand_plan(families, scenario)
    loads = compute_loads(demand_lines, families, resources)
    supply_lines = build_supply_plan(demand_lines, families, resources, scenario)
    finance_lines = build_finance_lines(supply_lines, families)
    summary = summarize(scenario, supply_lines, finance_lines)
    return loads, finance_lines, summary


class TestFillRateKpi(unittest.TestCase):
    def test_expressed_as_percent(self) -> None:
        families, resources = toy_families_and_resources()
        _, _, summary = _run(ScenarioId.CONSTRAINED, families, resources)
        k = fill_rate_kpi(ScenarioId.CONSTRAINED, summary)
        self.assertEqual(k.unit, "%")
        self.assertEqual(k.value, 50.0)


class TestBottleneckKpi(unittest.TestCase):
    def test_identifies_resource_and_flags_over_capacity(self) -> None:
        families, resources = toy_families_and_resources()
        loads, _, _ = _run(ScenarioId.UPSIDE, families, resources)
        k = bottleneck_kpi(resources, loads)
        self.assertEqual(k.value, 200.0)
        self.assertIn("RES-A", k.context)
        self.assertIn("exceeds installed capacity", k.context)

    def test_no_bottleneck_message_when_under_capacity(self) -> None:
        families, resources = toy_families_and_resources()
        loads, _, _ = _run(ScenarioId.BASE, families, resources)
        k = bottleneck_kpi(resources, loads)
        self.assertNotIn("exceeds installed capacity", k.context)


class TestLostMarginKpi(unittest.TestCase):
    def test_concentrates_in_the_lower_margin_family(self) -> None:
        families, resources = toy_families_and_resources()
        _, finance_lines, summary = _run(ScenarioId.CONSTRAINED, families, resources)
        k = lost_margin_kpi(summary, finance_lines)
        self.assertEqual(k.value, 4_800.0)
        self.assertIn("FAM-2", k.context)


class TestUpsideValueUnlockedKpi(unittest.TestCase):
    def test_delta_between_upside_and_constrained_margin(self) -> None:
        families, resources = toy_families_and_resources()
        _, _, upside_summary = _run(ScenarioId.UPSIDE, families, resources)
        _, _, constrained_summary = _run(ScenarioId.CONSTRAINED, families, resources)
        k = upside_value_unlocked_kpi(upside_summary, constrained_summary)
        self.assertEqual(k.value, upside_summary.total_gross_margin - constrained_summary.total_gross_margin)
        self.assertEqual(k.value, 4_800.0)  # exactly the lost margin, by construction


class TestComputeKpis(unittest.TestCase):
    def test_catalog_has_expected_keys(self) -> None:
        families, resources = toy_families_and_resources()
        loads_by, finance_by, summary_by = {}, {}, {}
        for scenario in (ScenarioId.BASE, ScenarioId.UPSIDE, ScenarioId.CONSTRAINED):
            loads, finance_lines, summary = _run(scenario, families, resources)
            loads_by[scenario] = loads
            finance_by[scenario] = finance_lines
            summary_by[scenario] = summary

        kpis = compute_kpis(resources, loads_by, summary_by, finance_by)
        for key in (
            "fill_rate_base", "fill_rate_upside", "fill_rate_constrained",
            "bottleneck", "lost_margin_constrained", "lost_revenue_constrained",
            "upside_value_unlocked",
        ):
            self.assertIn(key, kpis)


class TestPeakUtilizationTable(unittest.TestCase):
    def test_one_row_per_resource(self) -> None:
        families, resources = toy_families_and_resources()
        loads, _, _ = _run(ScenarioId.UPSIDE, families, resources)
        rows = peak_utilization_table(resources, loads)
        self.assertEqual(len(rows), len(resources))
        self.assertEqual(rows[0]["peak_utilization_pct"], 200.0)


if __name__ == "__main__":
    unittest.main()
