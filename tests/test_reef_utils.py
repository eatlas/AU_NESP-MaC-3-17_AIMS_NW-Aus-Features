"""Focused checks for countable-reef spatial assignment recovery."""

import unittest
from unittest.mock import patch

import geopandas as gpd
from geopandas.testing import assert_geodataframe_equal
from shapely.geometry import box

from reef_utils import cluster_countable


class CountableReefFallbackTests(unittest.TestCase):
    def setUp(self):
        self.reefs = gpd.GeoDataFrame({
            "RB_Type_L2": ["Coral Reef"] * 3,
            "geometry": [box(0, 0, 100, 100), box(150, 0, 250, 100),
                         box(500, 0, 600, 100)],
        }, index=[10, 20, 30], crs=3577)

    def test_fallback_recovers_missed_reef_without_changing_results(self):
        original = self.reefs.copy()
        expected, expected_stats = cluster_countable(self.reefs)
        spatial_join = gpd.sjoin

        def miss_first_assignment(*args, **kwargs):
            joined = spatial_join(*args, **kwargs)
            if kwargs["predicate"] == "within":
                joined.loc[20, ["_comp_id", "index_right"]] = float("nan")
            else:
                self.assertEqual(args[0]["_member_idx"].tolist(), [20])
                self.assertEqual(args[0].geom_type.tolist(), ["Point"])
            return joined

        with patch("reef_utils.gpd.sjoin", side_effect=miss_first_assignment) as join:
            actual, stats = cluster_countable(self.reefs)

        self.assertEqual(join.call_count, 2)
        self.assertEqual(stats, expected_stats)
        self.assertEqual(stats["n_unassigned"], 0)
        assert_geodataframe_equal(actual, expected)
        assert_geodataframe_equal(self.reefs, original)

    def test_failed_retry_reports_unassigned_reef(self):
        spatial_join = gpd.sjoin

        def miss_both_assignments(*args, **kwargs):
            joined = spatial_join(*args, **kwargs)
            joined.loc[20, ["_comp_id", "index_right"]] = float("nan")
            return joined

        with (patch("reef_utils.gpd.sjoin", side_effect=miss_both_assignments),
              patch("builtins.print") as report):
            actual, stats = cluster_countable(self.reefs)

        self.assertEqual(stats["n_unassigned"], 1)
        self.assertEqual(stats["n_countable"], 2)
        self.assertAlmostEqual(actual.Area_km2.sum(), 0.02)
        report.assert_called_once_with(
            "  WARNING: 1 'Coral Reef' reefs could not be assigned to a cluster")


if __name__ == "__main__":
    unittest.main()