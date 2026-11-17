"""Checks for A02 input configuration and countable-reef threshold precision."""

import importlib.util
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import geopandas as gpd
from shapely.geometry import box


SCRIPT = Path(__file__).resolve().parents[1] / "A02-unmapped-reefs.py"
spec = importlib.util.spec_from_file_location("unmapped_reefs", SCRIPT)
unmapped = importlib.util.module_from_spec(spec)
spec.loader.exec_module(unmapped)


class UnmappedReefTests(unittest.TestCase):
    def test_reference_paths_use_configured_directory(self):
        configured = unmapped.cfg.get("general", "in_3p_path")
        self.assertEqual(unmapped.in_3p_path, configured)
        for path in (unmapped.AHS_INPUT, unmapped.UNEP_INPUT, unmapped.GA_INPUT):
            self.assertTrue(Path(path).is_relative_to(Path(configured)))

    def test_builder_preserves_width_precision_at_threshold(self):
        widths = [99.951641, 100.04]
        sides = [width * math.sqrt(math.pi) / 2 for width in widths]
        reefs = gpd.GeoDataFrame({
            "RB_Type_L2": ["Coral Reef", "Coral Reef"],
            "geometry": [box(500 * index, 0, 500 * index + side, side)
                         for index, side in enumerate(sides)],
        }, crs=3577)
        with patch.object(unmapped.gpd, "read_file", return_value=reefs):
            clusters = unmapped.build_reef_clusters().sort_values("eff_wid_m")
        for actual, expected in zip(clusters.eff_wid_m, widths):
            self.assertAlmostEqual(actual, expected)
        self.assertEqual(clusters.size_class.tolist(), ["Very small", "Small"])

    def test_analysis_filters_before_rounding_exported_width(self):
        widths = [99.951641, 100.0, 100.04]
        clusters = gpd.GeoDataFrame({
            "cluster_id": [0, 1, 2],
            "eff_wid_m": widths,
            "size_class": [unmapped._classify_size(width) for width in widths],
            "geometry": [box(500 * index, 0, 500 * index + 10, 10)
                         for index in range(len(widths))],
        }, crs=4283)
        with (tempfile.TemporaryDirectory() as directory,
              patch.object(unmapped, "OUT_DIR", directory),
              patch.object(unmapped, "build_reef_clusters", return_value=clusters),
              patch.object(gpd.GeoDataFrame, "to_file", autospec=True) as save,
              patch.object(unmapped.gpd, "read_file",
                           side_effect=RuntimeError("Stop before loading references"))):
            with self.assertRaisesRegex(RuntimeError, "Stop before loading references"):
                unmapped.run_analysis()
        saved = save.call_args.args[0]
        self.assertEqual(saved.cluster_id.tolist(), [1, 2])
        self.assertEqual(saved.eff_wid_m.tolist(), [100.0, 100.0])
        self.assertEqual(saved.size_class.tolist(), ["Small", "Small"])
        self.assertEqual(clusters.eff_wid_m.tolist(), widths)


if __name__ == "__main__":
    unittest.main()