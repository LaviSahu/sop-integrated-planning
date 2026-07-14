"""Tests for datagen.py — the seeded synthetic Cascade Appliances dataset."""

import tempfile
import unittest
from pathlib import Path

import _bootstrap  # noqa: F401

from sop_integrated_planning import datagen
from sop_integrated_planning.models import jsonable


class TestGenerateFamilies(unittest.TestCase):
    def test_deterministic_across_runs(self) -> None:
        a = [jsonable(f) for f in datagen.generate_families()]
        b = [jsonable(f) for f in datagen.generate_families()]
        self.assertEqual(a, b)

    def test_family_count_and_ids_match_table(self) -> None:
        families = datagen.generate_families()
        self.assertEqual(len(families), len(datagen.FAMILY_TABLE))
        expected_ids = {row[0] for row in datagen.FAMILY_TABLE}
        self.assertEqual({f.id for f in families}, expected_ids)

    def test_monthly_demand_has_twelve_nonnegative_values(self) -> None:
        for family in datagen.generate_families():
            self.assertEqual(len(family.base_monthly_demand), 12)
            self.assertTrue(all(v >= 0.0 for v in family.base_monthly_demand))

    def test_different_seed_changes_jitter(self) -> None:
        a = datagen.generate_families(seed=1)
        b = datagen.generate_families(seed=2)
        # Same seasonal shape/average, but seeded jitter differs somewhere.
        self.assertNotEqual(
            [f.base_monthly_demand for f in a],
            [f.base_monthly_demand for f in b],
        )


class TestGenerateResources(unittest.TestCase):
    def test_resource_count_and_hours_match_table(self) -> None:
        resources = datagen.generate_resources()
        self.assertEqual(len(resources), len(datagen.RESOURCE_TABLE))
        by_id = {r.id: r.monthly_available_hours for r in resources}
        for rid, _name, hours in datagen.RESOURCE_TABLE:
            self.assertEqual(by_id[rid], hours)

    def test_resources_have_no_randomness(self) -> None:
        a = [r.monthly_available_hours for r in datagen.generate_resources()]
        b = [r.monthly_available_hours for r in datagen.generate_resources()]
        self.assertEqual(a, b)


class TestSeasonalIndex(unittest.TestCase):
    def test_normalizes_to_mean_one(self) -> None:
        for family_id in datagen.SEASONAL_SHAPE:
            index = datagen._seasonal_index(family_id)
            self.assertAlmostEqual(sum(index) / len(index), 1.0, places=4)


class TestWriteAndLoadRoundTrip(unittest.TestCase):
    def test_round_trip_preserves_data(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            families_path, resources_path = datagen.write_data(out_dir)
            self.assertTrue(families_path.exists())
            self.assertTrue(resources_path.exists())

            loaded_families = datagen.load_families(families_path)
            loaded_resources = datagen.load_resources(resources_path)
            original_families = datagen.generate_families()
            original_resources = datagen.generate_resources()

            self.assertEqual(
                [jsonable(f) for f in loaded_families],
                [jsonable(f) for f in original_families],
            )
            self.assertEqual(
                [jsonable(r) for r in loaded_resources],
                [jsonable(r) for r in original_resources],
            )


if __name__ == "__main__":
    unittest.main()
