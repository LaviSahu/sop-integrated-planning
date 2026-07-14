"""
cli.py — the command-line front door.

Four verbs, mirroring the monthly S&OP cycle's own escalation path (run
one view, compare the views, run the whole reconciliation, then hand
someone the dashboard):

- `plan SCENARIO`   — run one scenario end to end, print a console
  summary, optionally emit its full JSON payload.
- `compare`         — run all three scenarios and print them side by
  side: fill rate, revenue, gross margin, lost margin, the bottleneck,
  and what the upside is worth.
- `demo`            — the one-command showcase: (re)generate the seeded
  Cascade Appliances dataset, run all three scenarios, write
  `data/*.json` + `output/*.json`, and render `output/dashboard.html`.
- `dashboard`       — rebuild `output/dashboard.html` from `data/*.json`
  (generating it first if it doesn't exist yet) without re-running the
  console reports.

No third-party CLI framework — `argparse` plus a couple of hand-rolled,
dependency-free console-table helpers below.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import capacity as capacity_mod
from . import constrain as constrain_mod
from . import dashboard as dashboard_mod
from . import datagen
from . import demand as demand_mod
from . import finance as finance_mod
from . import kpi as kpi_mod
from .models import (
    Family,
    FinanceLine,
    FinanceSummary,
    Resource,
    ResourceLoad,
    ScenarioId,
    SupplyLine,
    jsonable,
)

ALL_SCENARIOS: tuple[ScenarioId, ...] = (ScenarioId.BASE, ScenarioId.UPSIDE, ScenarioId.CONSTRAINED)


# --------------------------------------------------------------------------
# Path resolution — the repo root is three levels above this file
# (src/sop_integrated_planning/cli.py -> src/sop_integrated_planning ->
# src -> repo root), so `data/` and `output/` resolve correctly no matter
# what directory the CLI is invoked from.
# --------------------------------------------------------------------------


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _default_data_dir() -> Path:
    return _repo_root() / "data"


def _default_output_dir() -> Path:
    return _repo_root() / "output"


# --------------------------------------------------------------------------
# Hand-rolled console table + ANSI helpers — no third-party dependency.
# --------------------------------------------------------------------------

_BOLD = "\033[1m"
_DIM = "\033[2m"
_RESET = "\033[0m"
_RED = "\033[31m"
_GREEN = "\033[32m"
_YELLOW = "\033[33m"


def _color_enabled() -> bool:
    return sys.stdout.isatty()


def _c(text: str, code: str) -> str:
    return f"{code}{text}{_RESET}" if _color_enabled() else text


def render_table(headers: list[str], rows: list[list[str]]) -> str:
    """A minimal, dependency-free fixed-width console table: left-aligned
    first column, right-aligned numeric columns, a dashed rule under the
    header."""
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(str(cell)))

    def fmt_row(cells: list[str]) -> str:
        parts = []
        for i, cell in enumerate(cells):
            text = str(cell)
            parts.append(text.ljust(widths[i]) if i == 0 else text.rjust(widths[i]))
        return "  ".join(parts)

    lines = [_c(fmt_row(headers), _BOLD)]
    lines.append(_c("  ".join("-" * w for w in widths), _DIM))
    for row in rows:
        lines.append(fmt_row([str(c) for c in row]))
    return "\n".join(lines)


def _fmt_money(v: float) -> str:
    sign = "-" if v < 0 else ""
    a = abs(v)
    return f"{sign}${a:,.0f}"


def _fmt_pct(v: float) -> str:
    return f"{v:.1f}%"


# --------------------------------------------------------------------------
# Pipeline orchestration — the one place every subcommand calls through.
# --------------------------------------------------------------------------


def run_scenario(
    families: list[Family],
    resources: list[Resource],
    scenario: ScenarioId,
) -> tuple[list[ResourceLoad], list[SupplyLine], list[FinanceLine], FinanceSummary]:
    """Run one scenario through the full engine chain: demand -> capacity ->
    constrained supply -> finance. Returns everything downstream consumers
    (console tables, JSON payloads, the dashboard) need."""
    demand_lines = demand_mod.build_demand_plan(families, scenario)
    loads = capacity_mod.compute_loads(demand_lines, families, resources)
    supply_lines = constrain_mod.build_supply_plan(demand_lines, families, resources, scenario)
    finance_lines = finance_mod.build_finance_lines(supply_lines, families)
    summary = finance_mod.summarize(scenario, supply_lines, finance_lines)
    return loads, supply_lines, finance_lines, summary


def run_all_scenarios(
    families: list[Family],
    resources: list[Resource],
) -> tuple[
    dict[ScenarioId, list[ResourceLoad]],
    dict[ScenarioId, list[SupplyLine]],
    dict[ScenarioId, list[FinanceLine]],
    dict[ScenarioId, FinanceSummary],
]:
    """Run BASE, UPSIDE, and CONSTRAINED and return four scenario-keyed dicts."""
    loads_by: dict[ScenarioId, list[ResourceLoad]] = {}
    supply_by: dict[ScenarioId, list[SupplyLine]] = {}
    finance_by: dict[ScenarioId, list[FinanceLine]] = {}
    summary_by: dict[ScenarioId, FinanceSummary] = {}
    for scenario in ALL_SCENARIOS:
        loads, supply_lines, finance_lines, summary = run_scenario(families, resources, scenario)
        loads_by[scenario] = loads
        supply_by[scenario] = supply_lines
        finance_by[scenario] = finance_lines
        summary_by[scenario] = summary
    return loads_by, supply_by, finance_by, summary_by


def _load_or_generate_dataset(data_dir: Path) -> tuple[list[Family], list[Resource]]:
    """Load the seeded dataset from `data_dir` if present, else generate +
    write it there first. Since generation is seeded, this is always
    reproducible either way."""
    families_path = data_dir / "families.json"
    resources_path = data_dir / "resources.json"
    if families_path.exists() and resources_path.exists():
        return datagen.load_families(families_path), datagen.load_resources(resources_path)
    datagen.write_data(data_dir)
    return datagen.load_families(families_path), datagen.load_resources(resources_path)


# --------------------------------------------------------------------------
# Console rendering shared by `plan` and `compare`.
# --------------------------------------------------------------------------


def _print_scenario_summary(scenario: ScenarioId, summary: FinanceSummary) -> None:
    print(_c(f"\n{scenario.value.upper()} scenario", _BOLD))
    rows = [
        ["Fill rate", _fmt_pct(summary.fill_rate * 100.0)],
        ["Revenue", _fmt_money(summary.total_revenue)],
        ["Gross margin", _fmt_money(summary.total_gross_margin)],
        ["Lost revenue", _fmt_money(summary.total_lost_revenue)],
        ["Lost margin", _fmt_money(summary.total_lost_margin)],
        ["Ending inventory value", _fmt_money(summary.ending_inventory_value)],
    ]
    print(render_table(["Metric", "Value"], rows))


def _print_capacity_table(resources: list[Resource], loads: list[ResourceLoad]) -> None:
    rows_data = kpi_mod.peak_utilization_table(resources, loads)
    rows = []
    for r in rows_data:
        pct = r["peak_utilization_pct"]
        pct_text = _fmt_pct(pct)
        if pct > 100.0:
            pct_text = _c(pct_text + " OVER", _RED)
        rows.append([r["resource_name"], f"{r['available_hours']:,.0f}", pct_text])
    print(render_table(["Resource", "Installed hrs/mo", "Peak utilization"], rows))


def _print_comparison(
    resources: list[Resource],
    loads_by: dict[ScenarioId, list[ResourceLoad]],
    summary_by: dict[ScenarioId, FinanceSummary],
    finance_by: dict[ScenarioId, list[FinanceLine]],
) -> None:
    kpis = kpi_mod.compute_kpis(resources, loads_by, summary_by, finance_by)

    print(_c("\nScenario comparison — Cascade Appliances (synthetic)", _BOLD))
    rows = []
    for label, key_fmt in [
        ("Fill rate", lambda s: _fmt_pct(summary_by[s].fill_rate * 100.0)),
        ("Revenue", lambda s: _fmt_money(summary_by[s].total_revenue)),
        ("Gross margin", lambda s: _fmt_money(summary_by[s].total_gross_margin)),
        ("Lost revenue", lambda s: _fmt_money(summary_by[s].total_lost_revenue)),
        ("Lost margin", lambda s: _fmt_money(summary_by[s].total_lost_margin)),
        ("Ending inventory value", lambda s: _fmt_money(summary_by[s].ending_inventory_value)),
    ]:
        rows.append([label] + [key_fmt(s) for s in ALL_SCENARIOS])
    print(render_table(["Metric", *[s.value.title() for s in ALL_SCENARIOS]], rows))

    print(_c("\nCapacity — peak utilization by resource (Upside demand plan)", _BOLD))
    _print_capacity_table(resources, loads_by[ScenarioId.UPSIDE])

    bn = kpis["bottleneck"]
    uv = kpis["upside_value_unlocked"]
    lm = kpis["lost_margin_constrained"]
    print(_c("\nExec takeaway", _BOLD))
    print(f"  Bottleneck: {bn.context} — {_fmt_pct(bn.value)} of installed capacity")
    print(f"  Upside value unlocked (if capacity is added): {_fmt_money(uv.value)}")
    print(f"  Margin at risk if not (constrained): {_fmt_money(lm.value)} ({lm.context})")


# --------------------------------------------------------------------------
# Subcommands
# --------------------------------------------------------------------------


def _cmd_plan(args: argparse.Namespace) -> int:
    scenario = ScenarioId(args.scenario)
    data_dir = args.data_dir or _default_data_dir()
    families, resources = _load_or_generate_dataset(data_dir)

    loads, supply_lines, finance_lines, summary = run_scenario(families, resources, scenario)

    _print_scenario_summary(scenario, summary)
    print(_c("\nCapacity — peak utilization by resource", _BOLD))
    _print_capacity_table(resources, loads)

    if args.json or args.out:
        payload = {
            "scenario": scenario.value,
            "summary": jsonable(summary),
            "loads": [jsonable(ld) for ld in loads],
            "supply_lines": [jsonable(sl) for sl in supply_lines],
            "finance_lines": [jsonable(fl) for fl in finance_lines],
        }
        text = json.dumps(payload, indent=2)
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(text, encoding="utf-8")
            print(f"\nWrote JSON payload to {args.out}")
        else:
            print("\n" + text)
    return 0


def _cmd_compare(args: argparse.Namespace) -> int:
    data_dir = args.data_dir or _default_data_dir()
    families, resources = _load_or_generate_dataset(data_dir)

    loads_by, supply_by, finance_by, summary_by = run_all_scenarios(families, resources)
    _print_comparison(resources, loads_by, summary_by, finance_by)

    if args.json or args.out:
        kpis = kpi_mod.compute_kpis(resources, loads_by, summary_by, finance_by)
        payload = {
            "summaries": {s.value: jsonable(summary_by[s]) for s in ALL_SCENARIOS},
            "kpis": {key: jsonable(k) for key, k in kpis.items()},
        }
        text = json.dumps(payload, indent=2)
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(text, encoding="utf-8")
            print(f"\nWrote JSON payload to {args.out}")
        else:
            print("\n" + text)
    return 0


def _cmd_demo(args: argparse.Namespace) -> int:
    data_dir = args.data_dir or _default_data_dir()
    output_dir = args.output_dir or _default_output_dir()

    print(_c("Generating seeded Cascade Appliances dataset...", _DIM))
    families_path, resources_path = datagen.write_data(data_dir)
    families = datagen.load_families(families_path)
    resources = datagen.load_resources(resources_path)
    print(f"  wrote {families_path}")
    print(f"  wrote {resources_path}")

    loads_by, supply_by, finance_by, summary_by = run_all_scenarios(families, resources)
    _print_comparison(resources, loads_by, summary_by, finance_by)

    kpis = kpi_mod.compute_kpis(resources, loads_by, summary_by, finance_by)
    generated_at = datetime.now(timezone.utc).isoformat()

    output_dir.mkdir(parents=True, exist_ok=True)
    comparison_payload = {
        "generated_at": generated_at,
        "summaries": {s.value: jsonable(summary_by[s]) for s in ALL_SCENARIOS},
        "kpis": {key: jsonable(k) for key, k in kpis.items()},
    }
    comparison_path = output_dir / "comparison.json"
    comparison_path.write_text(json.dumps(comparison_payload, indent=2), encoding="utf-8")

    context = dashboard_mod.build_context(
        families, resources, loads_by, supply_by, finance_by, summary_by, kpis, generated_at
    )
    dashboard_path = output_dir / "dashboard.html"
    dashboard_mod.render_dashboard(context, dashboard_path)

    print(_c("\nWrote:", _BOLD))
    print(f"  {comparison_path}")
    print(f"  {dashboard_path}")
    return 0


def _cmd_dashboard(args: argparse.Namespace) -> int:
    data_dir = args.data_dir or _default_data_dir()
    output_dir = args.output_dir or _default_output_dir()
    families, resources = _load_or_generate_dataset(data_dir)

    loads_by, supply_by, finance_by, summary_by = run_all_scenarios(families, resources)
    kpis = kpi_mod.compute_kpis(resources, loads_by, summary_by, finance_by)
    generated_at = datetime.now(timezone.utc).isoformat()

    context = dashboard_mod.build_context(
        families, resources, loads_by, supply_by, finance_by, summary_by, kpis, generated_at
    )
    dashboard_path = output_dir / "dashboard.html"
    dashboard_mod.render_dashboard(context, dashboard_path)
    print(f"Wrote {dashboard_path}")
    return 0


# --------------------------------------------------------------------------
# Argument parsing / entry point
# --------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sop_integrated_planning",
        description="S&OP / IBP decision cockpit for Cascade Appliances (synthetic demo data).",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_plan = subparsers.add_parser("plan", help="Run one scenario and print its plan (console + JSON).")
    p_plan.add_argument("scenario", choices=[s.value for s in ALL_SCENARIOS])
    p_plan.add_argument("--json", action="store_true", help="Also print the full JSON payload to stdout.")
    p_plan.add_argument("--out", type=Path, default=None, help="Write the JSON payload to this file.")
    p_plan.add_argument("--data-dir", type=Path, default=None, help="Directory holding families.json/resources.json.")
    p_plan.set_defaults(func=_cmd_plan)

    p_compare = subparsers.add_parser("compare", help="Run all three scenarios and print a comparison table.")
    p_compare.add_argument("--json", action="store_true", help="Also print the full JSON payload to stdout.")
    p_compare.add_argument("--out", type=Path, default=None, help="Write the JSON payload to this file.")
    p_compare.add_argument("--data-dir", type=Path, default=None)
    p_compare.set_defaults(func=_cmd_compare)

    p_demo = subparsers.add_parser(
        "demo", help="(Re)generate the dataset, run all scenarios, and render the dashboard."
    )
    p_demo.add_argument("--data-dir", type=Path, default=None)
    p_demo.add_argument("--output-dir", type=Path, default=None)
    p_demo.set_defaults(func=_cmd_demo)

    p_dash = subparsers.add_parser("dashboard", help="Rebuild output/dashboard.html from the current dataset.")
    p_dash.add_argument("--data-dir", type=Path, default=None)
    p_dash.add_argument("--output-dir", type=Path, default=None)
    p_dash.set_defaults(func=_cmd_dashboard)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
