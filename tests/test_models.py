"""Tests for models.py — the shared dataclass vocabulary and `jsonable()`."""

import unittest

import _bootstrap  # noqa: F401  (sys.path shim, must run before sop_integrated_planning imports)

from sop_integrated_planning.models import (
    Family,
    Kpi,
    Resource,
    ScenarioId,
    SCENARIO_LABELS,
    jsonable,
)


def _family() -> Family:
    return Family(
        id="FAM-1",
        name="Widget",
        unit_price=100.0,
        unit_variable_cost=37.5,
        opening_inventory_units=10.0,
        base_monthly_demand=[1.0, 2.0],
        upside_uplift_pct=0.2,
        resource_hours_per_unit={"RES-A": 2.0},
    )


class TestFamilyUnitMargin(unittest.TestCase):
    def test_margin_is_price_minus_cost(self) -> None:
        self.assertEqual(_family().unit_margin, 62.5)

    def test_margin_rounds_to_four_places(self) -> None:
        f = Family(
            id="FAM-X", name="X", unit_price=10.0 / 3.0, unit_variable_cost=0.0,
            opening_inventory_units=0.0, base_monthly_demand=[0.0], upside_uplift_pct=0.0,
        )
        self.assertEqual(f.unit_margin, round(10.0 / 3.0, 4))


class TestScenarioId(unittest.TestCase):
    def test_values_are_lowercase_strings(self) -> None:
        self.assertEqual(ScenarioId.BASE.value, "base")
        self.assertEqual(ScenarioId.UPSIDE.value, "upside")
        self.assertEqual(ScenarioId.CONSTRAINED.value, "constrained")

    def test_is_str_enum(self) -> None:
        self.assertEqual(ScenarioId.BASE, "base")

    def test_all_scenarios_labeled(self) -> None:
        for scenario in ScenarioId:
            self.assertIn(scenario, SCENARIO_LABELS)
            self.assertTrue(SCENARIO_LABELS[scenario])


class TestJsonable(unittest.TestCase):
    def test_family_dataclass_becomes_dict_with_injected_margin(self) -> None:
        result = jsonable(_family())
        self.assertEqual(result["id"], "FAM-1")
        self.assertEqual(result["unit_margin"], 62.5)
        self.assertEqual(result["resource_hours_per_unit"], {"RES-A": 2.0})

    def test_enum_becomes_its_value(self) -> None:
        self.assertEqual(jsonable(ScenarioId.CONSTRAINED), "constrained")

    def test_dict_and_list_recurse(self) -> None:
        payload = {"a": [ScenarioId.BASE, 1, 2.5], "b": {"nested": ScenarioId.UPSIDE}}
        result = jsonable(payload)
        self.assertEqual(result, {"a": ["base", 1, 2.5], "b": {"nested": "upside"}})

    def test_kpi_dataclass_round_trips_plain_fields(self) -> None:
        k = Kpi(key="k1", label="Label", value=12.34, unit="%", context="ctx")
        result = jsonable(k)
        self.assertEqual(result, {"key": "k1", "label": "Label", "value": 12.34, "unit": "%", "context": "ctx"})

    def test_resource_has_no_spurious_margin_field(self) -> None:
        r = Resource(id="RES-A", name="A", monthly_available_hours=100.0)
        result = jsonable(r)
        self.assertNotIn("unit_margin", result)


if __name__ == "__main__":
    unittest.main()
