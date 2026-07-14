"""
finance.py — reconciles the constrained supply plan into money.

This is the step that makes S&OP into Integrated Business Planning: per
Oliver Wight's *Transition from Sales and Operations Planning to
Integrated Business Planning* (2nd ed., 2022) and Palmatier & Crum's
*Enterprise Sales and Operations Planning*, IBP's defining move is
reconciling the operating plan (units, hours, inventory) with the
financial plan (revenue, margin, working capital) in the SAME monthly
cycle — not as a separate finance-only exercise weeks later. Every number
here is derived straight from `constrain.py`'s `SupplyLine` output:
nothing is re-estimated or hardcoded.

- **Revenue** = shipped units x unit price (what was actually sold, not
  what was demanded).
- **Gross margin** = shipped units x unit margin (price - variable cost).
- **Lost revenue / lost margin** = unmet units x price / margin — the
  value of demand that could have been sold but wasn't, because the
  supply plan couldn't produce it. In BASE and UPSIDE this is always
  zero by construction (both scenarios are built to fully clear demand);
  in CONSTRAINED it is the real cost of not adding capacity.
- **Inventory value** = ending inventory units x unit variable cost
  (goods carried at cost, not at selling price).
"""

from __future__ import annotations

from .models import Family, FinanceLine, FinanceSummary, ScenarioId, SupplyLine


def build_finance_lines(supply_lines: list[SupplyLine], families: list[Family]) -> list[FinanceLine]:
    """One FinanceLine per (family, month) in the supply plan."""
    families_by_id = {f.id: f for f in families}
    lines: list[FinanceLine] = []
    for sl in supply_lines:
        family = families_by_id[sl.family_id]
        lines.append(
            FinanceLine(
                scenario=sl.scenario,
                family_id=sl.family_id,
                month=sl.month,
                revenue=round(sl.shipped_units * family.unit_price, 2),
                gross_margin=round(sl.shipped_units * family.unit_margin, 2),
                lost_revenue=round(sl.unmet_units * family.unit_price, 2),
                lost_margin=round(sl.unmet_units * family.unit_margin, 2),
                inventory_value=round(sl.ending_inventory_units * family.unit_variable_cost, 2),
            )
        )
    return lines


def summarize(scenario: ScenarioId, supply_lines: list[SupplyLine], finance_lines: list[FinanceLine]) -> FinanceSummary:
    """Roll every FinanceLine + SupplyLine up into one scenario-level summary."""
    total_demand = sum(sl.demand_units for sl in supply_lines)
    total_shipped = sum(sl.shipped_units for sl in supply_lines)
    fill_rate = round(total_shipped / total_demand, 4) if total_demand > 0 else 1.0

    # Ending inventory value is a point-in-time balance (December's close),
    # not a sum across months, or it would double-count carried stock.
    december_lines = [fl for fl in finance_lines if fl.month == 12]
    ending_inventory_value = round(sum(fl.inventory_value for fl in december_lines), 2)

    return FinanceSummary(
        scenario=scenario,
        total_revenue=round(sum(fl.revenue for fl in finance_lines), 2),
        total_gross_margin=round(sum(fl.gross_margin for fl in finance_lines), 2),
        total_lost_revenue=round(sum(fl.lost_revenue for fl in finance_lines), 2),
        total_lost_margin=round(sum(fl.lost_margin for fl in finance_lines), 2),
        ending_inventory_value=ending_inventory_value,
        fill_rate=fill_rate,
    )


def gross_margin_by_family(finance_lines: list[FinanceLine]) -> dict[str, float]:
    """Full-year gross margin per family, for the reconciliation table."""
    totals: dict[str, float] = {}
    for fl in finance_lines:
        totals[fl.family_id] = totals.get(fl.family_id, 0.0) + fl.gross_margin
    return {k: round(v, 2) for k, v in totals.items()}


def lost_margin_by_family(finance_lines: list[FinanceLine]) -> dict[str, float]:
    """Full-year lost margin per family — where the money left on the table concentrates."""
    totals: dict[str, float] = {}
    for fl in finance_lines:
        totals[fl.family_id] = totals.get(fl.family_id, 0.0) + fl.lost_margin
    return {k: round(v, 2) for k, v in totals.items()}
