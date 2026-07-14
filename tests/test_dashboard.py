"""Tests for dashboard.py — context assembly and the self-contained HTML render."""

import json
import tempfile
import unittest
from pathlib import Path

import _bootstrap  # noqa: F401

from fixtures import toy_families_and_resources

from sop_integrated_planning.capacity import compute_loads
from sop_integrated_planning.constrain import build_supply_plan
from sop_integrated_planning.dashboard import build_context, render_dashboard
from sop_integrated_planning.demand import build_demand_plan
from sop_integrated_planning.finance import build_finance_lines, summarize
from sop_integrated_planning.kpi import compute_kpis
from sop_integrated_planning.models import ScenarioId


def _full_context():
    families, resources = toy_families_and_resources()
    loads_by, supply_by, finance_by, summary_by = {}, {}, {}, {}
    for scenario in (ScenarioId.BASE, ScenarioId.UPSIDE, ScenarioId.CONSTRAINED):
        demand_lines = build_demand_plan(families, scenario)
        loads = compute_loads(demand_lines, families, resources)
        supply_lines = build_supply_plan(demand_lines, families, resources, scenario)
        finance_lines = build_finance_lines(supply_lines, families)
        summary = summarize(scenario, supply_lines, finance_lines)
        loads_by[scenario] = loads
        supply_by[scenario] = supply_lines
        finance_by[scenario] = finance_lines
        summary_by[scenario] = summary
    kpis = compute_kpis(resources, loads_by, summary_by, finance_by)
    context = build_context(
        families, resources, loads_by, supply_by, finance_by, summary_by, kpis, "2026-07-14T00:00:00+00:00"
    )
    return context


class TestBuildContext(unittest.TestCase):
    def test_top_level_keys_present(self) -> None:
        context = _full_context()
        for key in ("generated_at", "company", "kpis", "resources", "families", "scenarios", "bottleneck"):
            self.assertIn(key, context)

    def test_all_three_scenarios_present(self) -> None:
        context = _full_context()
        self.assertEqual(set(context["scenarios"].keys()), {"base", "upside", "constrained"})

    def test_bottleneck_identifies_the_over_capacity_resource(self) -> None:
        context = _full_context()
        self.assertIsNotNone(context["bottleneck"])
        self.assertEqual(context["bottleneck"]["resource_id"], "RES-A")
        self.assertEqual(context["bottleneck"]["utilization_pct"], 200.0)

    def test_context_is_json_serializable(self) -> None:
        context = _full_context()
        # Would raise if any non-primitive (Enum, dataclass, date) leaked through.
        json.dumps(context)


class TestRenderDashboard(unittest.TestCase):
    def test_writes_self_contained_html(self) -> None:
        context = _full_context()
        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / "dashboard.html"
            render_dashboard(context, out_path)
            self.assertTrue(out_path.exists())
            html = out_path.read_text(encoding="utf-8")

            self.assertIn("<title>", html)
            self.assertIn("Cascade Appliances", html)
            # No CDN/network dependency of any kind.
            self.assertNotIn("http://", html)
            self.assertNotIn("https://", html)
            self.assertNotIn("<script src=", html)
            self.assertNotIn("<link ", html)

    def test_embedded_json_survives_a_closing_script_tag_in_the_data(self) -> None:
        context = _full_context()
        context["company"] = "Cascade </script><script>alert(1)</script> Appliances"
        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / "dashboard.html"
            render_dashboard(context, out_path)
            html = out_path.read_text(encoding="utf-8")
            # The dangerous literal must never appear un-escaped.
            self.assertNotIn("</script><script>alert(1)</script>", html)
            self.assertIn("<\\/script>", html)


if __name__ == "__main__":
    unittest.main()
