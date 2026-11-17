"""Focused checks for the A07 habitat and reef area comparison."""

import csv
import importlib.util
from pathlib import Path
import tempfile
import unittest

import geopandas as gpd
from shapely.geometry import box


SCRIPT = Path(__file__).resolve().parents[1] / "A07-coral-area-comparison.py"
spec = importlib.util.spec_from_file_location("coral_comparison", SCRIPT)
comparison = importlib.util.module_from_spec(spec)
spec.loader.exec_module(comparison)


class CoralAreaComparisonTests(unittest.TestCase):
    def test_clipping_uses_all_l3_coral_geometries(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            regions = gpd.GeoDataFrame({
                "subregion": list(comparison.SUBREGIONS),
                "geometry": [box(100 * index, 0, 100 * (index + 1), 100)
                             for index in range(6)],
            }, crs=3577)
            reefs = gpd.GeoDataFrame({
                "RB_Type_L3": ["Coral Reef", "Coral Reef", "Coral Reef Flat"],
                "Area_km2": [99, 99, 99],
                "geometry": [box(50, 0, 150, 100), box(0, 0, 1, 1),
                             box(200, 0, 300, 100)],
            }, crs=3577)
            region_path, reef_path = root / "regions.gpkg", root / "reefs.gpkg"
            regions.to_file(region_path)
            reefs.to_file(reef_path)

            areas = comparison.boundary_areas(reef_path, region_path)
            self.assertAlmostEqual(areas[comparison.SUBREGIONS[0]], 0.005001)
            self.assertAlmostEqual(areas[comparison.SUBREGIONS[1]], 0.005)
            self.assertEqual(areas[comparison.SUBREGIONS[2]], 0)

    def test_habitat_requires_one_matching_row_per_subregion(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "habitat.csv"
            header = ["Regionalisation", "Region_name", "Mapping", "Class_id",
                      "Class_name", "Area_km2"]
            rows = [["Analysis-regions v1", name, "Benthic", "15",
                     "Coral/Algae", "1.234567"] for name in comparison.SUBREGIONS]

            def write_rows(values):
                with path.open("w", newline="", encoding="utf-8") as output:
                    writer = csv.writer(output)
                    writer.writerow(header)
                    writer.writerows(values)

            write_rows(rows)
            self.assertEqual(len(comparison.habitat_areas(path)), 6)
            write_rows(rows + [rows[0]])
            with self.assertRaisesRegex(ValueError, "Duplicate habitat area"):
                comparison.habitat_areas(path)
            write_rows(rows[:-1])
            with self.assertRaisesRegex(ValueError, "Missing habitat areas"):
                comparison.habitat_areas(path)


if __name__ == "__main__":
    unittest.main()