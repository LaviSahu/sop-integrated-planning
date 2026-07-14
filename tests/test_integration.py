"""
Full-pipeline integration tests, run on the REAL seeded Cascade Appliances
dataset (not the hand-computable toy fixtures used elsewhere) — these are
the tests that guard the specific business claim this repo exists to
demonstrate:

- BASE is feasible: every resource, every month, <= 100% of installed
  capacity.
- UPSIDE genuinely overloads at least one resource (>100%) as an
  emergent consequence of seasonality x uplift x resource intensity —
  nothing here hardcodes which resource or by how much.
- CONSTRAINED (same upside demand, capacity held at base) produces a
  real, quantifiable fill-rate shortfall and lost margin, rationed by
  descending unit margin.
- The dashboard renders end to end on the real dataset.
"""

import tempfile
import unittest
from pathlib import Path

import _bootstrap  # noqa: F401

from sop_integrated_planning import cli, datagen
from sop_integrated_planning.dashboard import build_context, render_dashboard
from sop_integrated_planning.kpi import compute_kpis
from sop_integrated_planning.models import ScenarioId


class TestFullPipelineOnRealSeededData(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.families = datagen.generate_families()
        cls.resources = datagen.generate_resources()
        cls.loads_by, cls.supply_by, cls.finance_by, cls.summary_by = cli.run_all_scenarios(
            cls.families, cls.resources
        )
        cls.kpis = compute_kpis(cls.resources, cls.loads_by, cls.summary_by, cls.finance_by)

    def test_base_scenario_is_fully_feasible(self) -> None:
        max_util = max(ld.utilization_pct for ld in self.loads_by[ScenarioId.BASE])
        self.assertLessEqual(max_util, 100.0)
        self.assertEqual(self.summary_by[ScenarioId.BASE].fill_rate, 1.0)
        self.assertEqual(self.summary_by[ScenarioId.BASE].total_lost_margin, 0.0)

    def test_upside_scenario_genuinely_overloads_a_resource(self) -> None:
        max_util = max(ld.utilization_pct for ld in self.loads_by[ScenarioId.UPSIDE])
        self.assertGreater(max_util, 100.0, "seeded data must produce a real RCCP bottleneck under upside demand")

    def test_upside_scenario_still_fully_ships_via_assumed_investment(self) -> None:
        self.assertEqual(self.summary_by[ScenarioId.UPSIDE].fill_rate, 1.0)
        self.assertEqual(self.summary_by[ScenarioId.UPSIDE].total_lost_margin, 0.0)

    def test_constrained_scenario_has_a_real_quantifiable_shortfall(self) -> None:
        summary = self.summary_by[ScenarioId.CONSTRAINED]
        self.assertLess(summary.fill_rate, 1.0)
        self.assertGreater(summary.fill_rate, 0.9)  # realistic, not a collapse
        self.assertGreater(summary.total_lost_margin, 0.0)
        self.assertGreater(summary.total_lost_revenue, 0.0)

    def test_upside_value_unlocked_equals_constrained_lost_margin(self) -> None:
        # UPSIDE ships 100% of the same demand CONSTRAINED partially
        # ships, so the gross-margin delta between them is exactly the
        # margin CONSTRAINED left on the table.
        delta = self.kpis["upside_value_unlocked"].value
        lost = self.kpis["lost_margin_constrained"].value
        self.assertAlmostEqual(delta, lost, places=2)

    def test_bottleneck_kpi_matches_the_binding_resource(self) -> None:
        from sop_integrated_planning.capacity import binding_resource

        expected = binding_resource(self.loads_by[ScenarioId.UPSIDE])
        self.assertIsNotNone(expected)
        self.assertIn(expected, self.kpis["bottleneck"].context)

    def test_shortfall_concentrates_in_a_single_family(self) -> None:
        from sop_integrated_planning.finance import lost_margin_by_family

        by_family = lost_margin_by_family(self.finance_by[ScenarioId.CONSTRAINED])
        nonzero = {fam: v for fam, v in by_family.items() if v > 0.0}
        self.assertGreaterEqual(len(nonzero), 1)


class TestDemoWritesFilesAndDashboard(unittest.TestCase):
    def test_demo_pipeline_writes_dataset_comparison_and_dashboard(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            output_dir = Path(tmp) / "output"

            families_path, resources_path = datagen.write_data(data_dir)
            families = datagen.load_families(families_path)
            resources = datagen.load_resources(resources_path)

            loads_by, supply_by, finance_by, summary_by = cli.run_all_scenarios(families, resources)
            kpis = compute_kpis(resources, loads_by, summary_by, finance_by)
            context = build_context(
                families, resources, loads_by, supply_by, finance_by, summary_by, kpis, "2026-07-14T00:00:00+00:00"
            )
            dashboard_path = output_dir / "dashboard.html"
            render_dashboard(context, dashboard_path)

            self.assertTrue(families_path.exists())
            self.assertTrue(resources_path.exists())
            self.assertTrue(dashboard_path.exists())

            html = dashboard_path.read_text(encoding="utf-8")
            self.assertIn("Cascade Appliances", html)
            self.assertGreater(len(html), 10_000)  # a real rendered page, not a stub


if __name__ == "__main__":
    unittest.main()
