"""
datagen.py — generates the synthetic Cascade Appliances dataset.

Everything downstream of this module — demand plans, capacity checks,
constrained supply, financial reconciliation, the dashboard — runs on
data produced here. It is entirely synthetic and entirely seeded: run it
twice and you get byte-identical `data/families.json` /
`data/resources.json`. There is no real company called "Cascade
Appliances"; the six product families, four production resources, prices,
costs, and seasonal demand curves below are invented for this repo.

**Why these specific numbers.** The brief for this repo is a deliberate
modeling tension: the BASE demand plan must be feasible against installed
capacity (S&OP's "we already agreed to this" plan), while the UPSIDE
demand overlay must genuinely overload at least one shared production
resource — not because a number is hardcoded to say so, but because the
seasonality, the uplift percentages, and the resource-hour intensities
multiply out that way. `RESOURCE_CAPACITY_HOURS` and the per-family
`UPSIDE_UPLIFT_PCT` were tuned (see `implementation-notes.md`) so that:
Assembly Line A — the resource the three highest-uplift families
(Refrigerators, Washers, Dryers) lean on hardest — clears 100% utilization
in the seasonal peak months once the upside overlay is added, while every
other resource, and Line A itself under the base plan, stays under 100%.
That tension is the whole point of running three scenarios instead of one.

Seasonality: appliances see two real demand shapes — a spring
remodel/relocation bump (Mar-May) and a Q4 holiday/promotion bump
(Nov-Dec) — approximated here as family-specific monthly index curves,
normalized to average 1.0 across the year so the annual total matches the
stated average monthly demand exactly.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

from .models import Family, Resource

SEED = 20260714  # fixed seed -> stable, reproducible synthetic data
_NOISE_PCT = 0.03  # +/-3% multiplicative jitter per family/month, seeded

MONTHS = list(range(1, 13))

# --------------------------------------------------------------------------
# Resources — shared production stages every family competes for.
# `monthly_available_hours` is INSTALLED (base) capacity: it does not move
# just because someone hopes for more demand. See constrain.py for how a
# scenario can decide to invest beyond this baseline.
# --------------------------------------------------------------------------

RESOURCE_TABLE: list[tuple[str, str, float]] = [
    # id             name                    monthly_available_hours
    ("RES-LINEA", "Assembly Line A (heavy)", 9_500.0),
    ("RES-LINEB", "Assembly Line B (light)", 7_800.0),
    ("RES-QA", "Test / QA", 2_220.0),
    ("RES-PKG", "Packaging", 1_600.0),
]

# --------------------------------------------------------------------------
# Families — id, name, unit price, unit variable cost, opening inventory
# (units), average monthly base demand (units), upside uplift (promotion /
# market-growth overlay, applied in UPSIDE and CONSTRAINED scenarios only).
# --------------------------------------------------------------------------

FAMILY_TABLE: list[tuple[str, str, float, float, float, float, float]] = [
    # id           name            price    var_cost  open_inv  avg_demand  upside_uplift_pct
    ("FAM-REF", "Refrigerators", 1_349.00, 812.00, 4_200.0, 3_000.0, 0.25),
    ("FAM-WSH", "Washers", 799.00, 471.00, 3_100.0, 2_500.0, 0.20),
    ("FAM-DRY", "Dryers", 699.00, 402.00, 2_600.0, 2_000.0, 0.15),
    ("FAM-MWV", "Microwaves", 179.00, 96.00, 6_500.0, 4_000.0, 0.00),
    ("FAM-DSH", "Dishwashers", 649.00, 381.00, 2_200.0, 1_800.0, 0.10),
    ("FAM-RNG", "Ranges", 899.00, 549.00, 1_900.0, 1_500.0, 0.00),
]

# Resource-hours consumed per unit produced, by family. Refrigerators /
# Washers / Dryers (the three families carrying an upside uplift) are the
# heavy Assembly-Line-A users; Microwaves / Dishwashers / Ranges run on
# the lighter Line B. Every family also draws Test/QA and Packaging hours.
HOURS_PER_UNIT: dict[str, dict[str, float]] = {
    "FAM-REF": {"RES-LINEA": 1.20, "RES-QA": 0.15, "RES-PKG": 0.10},
    "FAM-WSH": {"RES-LINEA": 0.80, "RES-QA": 0.12, "RES-PKG": 0.08},
    "FAM-DRY": {"RES-LINEA": 0.70, "RES-QA": 0.10, "RES-PKG": 0.08},
    "FAM-MWV": {"RES-LINEB": 0.25, "RES-QA": 0.05, "RES-PKG": 0.04},
    "FAM-DSH": {"RES-LINEB": 0.90, "RES-QA": 0.12, "RES-PKG": 0.07},
    "FAM-RNG": {"RES-LINEB": 0.75, "RES-QA": 0.10, "RES-PKG": 0.06},
}

# Raw seasonal shape per family, by calendar month (1=Jan .. 12=Dec).
# Normalized to average 1.0 inside `_seasonal_index` so the annual total
# always matches the family's stated average monthly demand exactly,
# regardless of how the raw shape below is edited.
SEASONAL_SHAPE: dict[str, list[float]] = {
    # Refrigerators: spring home-buying/remodel season peak (Mar-May),
    # a smaller Q4 promotion bump.
    "FAM-REF": [0.85, 0.85, 1.25, 1.35, 1.30, 1.00, 0.90, 0.85, 0.85, 0.90, 1.15, 1.20],
    # Washers/Dryers: same spring remodel bump, plus a January
    # New-Year replacement bump.
    "FAM-WSH": [1.05, 0.90, 1.20, 1.30, 1.25, 1.00, 0.90, 0.85, 0.85, 0.90, 1.10, 1.15],
    "FAM-DRY": [1.05, 0.90, 1.20, 1.30, 1.25, 1.00, 0.90, 0.85, 0.85, 0.90, 1.10, 1.15],
    # Microwaves: flattest curve, small Q4 gifting bump.
    "FAM-MWV": [0.95, 0.90, 0.95, 1.00, 1.00, 0.95, 0.90, 0.90, 0.95, 1.00, 1.20, 1.30],
    # Dishwashers: mild spring remodel echo.
    "FAM-DSH": [0.90, 0.90, 1.10, 1.20, 1.15, 1.00, 0.90, 0.90, 0.90, 0.95, 1.05, 1.05],
    # Ranges: mild spring remodel echo + Thanksgiving/holiday cooking bump.
    "FAM-RNG": [0.90, 0.90, 1.05, 1.15, 1.10, 0.95, 0.90, 0.90, 0.90, 1.05, 1.20, 1.10],
}


def _seasonal_index(family_id: str) -> list[float]:
    """Normalize a raw seasonal shape to average exactly 1.0 across 12 months."""
    raw = SEASONAL_SHAPE[family_id]
    mean = sum(raw) / len(raw)
    return [round(v / mean, 6) for v in raw]


def _monthly_base_demand(avg_demand: float, family_id: str, rng: random.Random) -> list[float]:
    """Seasonality-shaped monthly demand with small seeded jitter, floored at 0."""
    index = _seasonal_index(family_id)
    demand = []
    for month_idx in index:
        jitter = 1.0 + rng.uniform(-_NOISE_PCT, _NOISE_PCT)
        demand.append(round(max(0.0, avg_demand * month_idx * jitter), 1))
    return demand


def generate_families(seed: int = SEED) -> list[Family]:
    """Build the seeded Family list. Deterministic: same seed -> same output."""
    rng = random.Random(seed)
    families = []
    for fam_id, name, price, cost, opening_inv, avg_demand, uplift in FAMILY_TABLE:
        families.append(
            Family(
                id=fam_id,
                name=name,
                unit_price=price,
                unit_variable_cost=cost,
                opening_inventory_units=opening_inv,
                base_monthly_demand=_monthly_base_demand(avg_demand, fam_id, rng),
                upside_uplift_pct=uplift,
                resource_hours_per_unit=dict(HOURS_PER_UNIT[fam_id]),
            )
        )
    return families


def generate_resources() -> list[Resource]:
    """Build the Resource list. No randomness — capacity is a fixed install."""
    return [Resource(id=rid, name=name, monthly_available_hours=hours) for rid, name, hours in RESOURCE_TABLE]


def write_data(out_dir: Path | str = "data", seed: int = SEED) -> tuple[Path, Path]:
    """Generate families + resources and write them as JSON to `out_dir`."""
    from .models import jsonable

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    families = generate_families(seed)
    resources = generate_resources()

    families_path = out / "families.json"
    resources_path = out / "resources.json"
    families_path.write_text(json.dumps([jsonable(f) for f in families], indent=2), encoding="utf-8")
    resources_path.write_text(json.dumps([jsonable(r) for r in resources], indent=2), encoding="utf-8")
    return families_path, resources_path


def load_families(path: Path | str = "data/families.json") -> list[Family]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return [
        Family(
            id=r["id"],
            name=r["name"],
            unit_price=r["unit_price"],
            unit_variable_cost=r["unit_variable_cost"],
            opening_inventory_units=r["opening_inventory_units"],
            base_monthly_demand=list(r["base_monthly_demand"]),
            upside_uplift_pct=r["upside_uplift_pct"],
            resource_hours_per_unit=dict(r["resource_hours_per_unit"]),
        )
        for r in raw
    ]


def load_resources(path: Path | str = "data/resources.json") -> list[Resource]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return [Resource(id=r["id"], name=r["name"], monthly_available_hours=r["monthly_available_hours"]) for r in raw]


if __name__ == "__main__":
    fp, rp = write_data()
    print(f"wrote {fp} and {rp}")
