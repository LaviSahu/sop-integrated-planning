"""Tests for cli.py — console formatting helpers, argument parsing, and orchestration."""

import unittest

import _bootstrap  # noqa: F401

from fixtures import toy_families_and_resources

from sop_integrated_planning import cli
from sop_integrated_planning.models import ScenarioId


class TestFormatting(unittest.TestCase):
    def test_fmt_money_formats_thousands_with_commas(self) -> None:
        self.assertEqual(cli._fmt_money(1_234_567.0), "$1,234,567")

    def test_fmt_money_handles_negative(self) -> None:
        self.assertEqual(cli._fmt_money(-500.0), "-$500")

    def test_fmt_pct_one_decimal(self) -> None:
        self.assertEqual(cli._fmt_pct(99.949), "99.9%")


class TestRenderTable(unittest.TestCase):
    def test_columns_align_and_header_present(self) -> None:
        text = cli.render_table(["Name", "Value"], [["Fill rate", "100.0%"], ["Revenue", "$1,000"]])
        lines = text.splitlines()
        self.assertIn("Name", lines[0])
        self.assertIn("Value", lines[0])
        self.assertEqual(len(lines), 4)  # header + rule + 2 rows


class TestBuildParser(unittest.TestCase):
    def test_plan_requires_a_valid_scenario(self) -> None:
        parser = cli.build_parser()
        args = parser.parse_args(["plan", "base"])
        self.assertEqual(args.scenario, "base")
        self.assertEqual(args.command, "plan")

    def test_plan_rejects_unknown_scenario(self) -> None:
        parser = cli.build_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args(["plan", "nonsense"])

    def test_all_four_subcommands_registered(self) -> None:
        parser = cli.build_parser()
        for command, extra in [("plan", ["base"]), ("compare", []), ("demo", []), ("dashboard", [])]:
            args = parser.parse_args([command, *extra])
            self.assertEqual(args.command, command)


class TestRunScenarioOrchestration(unittest.TestCase):
    def test_run_scenario_matches_hand_computed_constrained_result(self) -> None:
        families, resources = toy_families_and_resources()
        loads, supply_lines, finance_lines, summary = cli.run_scenario(families, resources, ScenarioId.CONSTRAINED)
        self.assertAlmostEqual(summary.fill_rate, 0.5, places=4)
        self.assertEqual(summary.total_lost_margin, 4_800.0)
        self.assertTrue(any(ld.is_bottleneck for ld in loads))

    def test_run_all_scenarios_returns_all_three_keys(self) -> None:
        families, resources = toy_families_and_resources()
        loads_by, supply_by, finance_by, summary_by = cli.run_all_scenarios(families, resources)
        for d in (loads_by, supply_by, finance_by, summary_by):
            self.assertEqual(set(d.keys()), {ScenarioId.BASE, ScenarioId.UPSIDE, ScenarioId.CONSTRAINED})


if __name__ == "__main__":
    unittest.main()
