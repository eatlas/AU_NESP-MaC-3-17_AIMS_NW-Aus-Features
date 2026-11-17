"""Small geometry checks for the A05 regional allocation."""

import csv
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import geopandas as gpd
from shapely.geometry import Polygon, box


SCRIPT = Path(__file__).resolve().parents[1] / "A05-reef-distribution.py"
spec = importlib.util.spec_from_file_location("reef_distribution", SCRIPT)
distribution = importlib.util.module_from_spec(spec)
spec.loader.exec_module(distribution)


class ReefDistributionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        work = Path(self.directory.name)
        work_patch = patch.object(distribution, "WORK_DIR", work)
        csv_patch = patch.object(distribution, "OUTPUT_CSV", work / "summary.csv")
        work_patch.start()
        csv_patch.start()
        self.addCleanup(work_patch.stop)
        self.addCleanup(csv_patch.stop)
        self.setting = dict(distribution.REGIONALISATIONS[1], name="Sample", slug="test")
        self.capad = dict(distribution.REGIONALISATIONS[2], near_m=None)

    def slice_and_assign(self, reefs, regions, setting):
        pieces = distribution.slice_reefs(reefs, regions, None, setting)
        areas = reefs.set_index("CountFID").geometry.area / 1e6
        return distribution.assign_counts(pieces, areas)

    def test_slicing_slivers_and_summary(self):
        reefs = gpd.GeoDataFrame({
            "CountFID": [1, 2], "RB_Type_L2": ["Coral Reef", "Rocky Reef"],
            "geometry": [box(0, 0, 100, 40), box(120, 0, 140, 20)],
        }, crs=3577)
        regions = gpd.GeoDataFrame({
            "TYPE": ["", "", ""], "NAME": ["A", "B", "Thin"],
            "geometry": [box(-10, -10, 50, 50), box(50, -10, 70, 50),
                         box(98, -10, 100, 50)],
        }, crs=3577)

        distribution.check_overlaps(regions, "test")
        portions = self.slice_and_assign(reefs, regions, self.setting)
        self.assertEqual(set(portions.NAME), {"A", "B", "Thin", "No match"})
        self.assertEqual(len(portions), 5)
        self.assertEqual(portions.loc[portions.NAME == "Thin", "Sliver"].iloc[0], 1)
        self.assertEqual(portions.loc[portions.NAME == "A", "Area_km2"].iloc[0],
                         0.002)
        self.assertAlmostEqual(portions.Area_km2.sum(), 4400 / 1e6)
        self.assertAlmostEqual(portions.loc[portions.Sliver == 0, "Area_km2"].sum(),
                       (4400 - 80) / 1e6)
        cached = self.slice_and_assign(reefs, regions, self.setting)
        self.assertEqual(len(cached), 5)
        self.assertEqual(cached.Assigned.tolist(), portions.Assigned.tolist())
        checks = distribution.check_conservation(portions, reefs, "Sample")
        self.assertEqual([row["Status"] for row in checks], ["Pass", "Pass"])

        records_for_export = distribution.summarise([("Sample", portions)])
        with distribution.OUTPUT_CSV.open(newline="", encoding="utf-8") as output:
            records = list(csv.DictReader(output))
        self.assertEqual([row["Region_name"] for row in records],
                         ["A", "B", "No match"])
        self.assertEqual([row["Region_type"] for row in records], ["", "", ""])
        self.assertEqual(records[-1]["Coral_reef_count"], "0")
        self.assertEqual(records[-1]["Coral_reef_partial_count"], "1")
        self.assertEqual(records[-1]["Rocky_reef_count"], "1")
        self.assertEqual(records[-1]["Coral_reef_area_km2"], "0.001120")

        distribution.export_region_stats(regions, None, records_for_export, self.setting)
        exported = gpd.read_file(
            distribution.OUTPUT_CSV.parent /
            f"A05_Region-stats_test_{distribution.VERSION}.shp"
        )
        self.assertEqual(set(exported.RegionName), {"A", "B"})
        self.assertEqual(set(exported.columns), {"RegionName", "Near", "Label",
                             "CoralCount", "CoralPart", "CoralKm2",
                             "RockyCount", "RockyPart", "RockyKm2",
                             "geometry"})
        first = exported.set_index("RegionName").loc["A"]
        self.assertEqual(first.CoralCount, 1)
        self.assertEqual(first.RockyCount, 0)
        self.assertEqual(first.CoralKm2, 0.002)
        self.assertTrue(first.geometry.equals(regions.geometry.iloc[0]))

    def test_export_keeps_separate_polygons_with_same_region_name(self):
        regions = gpd.GeoDataFrame({
            "TYPE": ["", "", ""], "NAME": ["A", "A", "Empty"],
            "geometry": [box(0, 0, 10, 10), box(20, 0, 30, 10),
                         box(40, 0, 50, 10)],
        }, crs=3577)
        record = {"Region_dataset": "Sample", "Region_type": "", "Region_name": "A",
                "Near_region": "No", "Label": "A", "Coral_reef_count": 2,
                "Coral_reef_partial_count": 0, "Coral_reef_area_km2": "0.000200",
                "Rocky_reef_count": 0, "Rocky_reef_partial_count": 0,
                "Rocky_reef_area_km2": "0.000000"}
        records = [record, dict(record, Region_name="No match", Label="No match",
                        Coral_reef_count=1, Coral_reef_area_km2="0.000100")]
        distribution.export_region_stats(regions, None, records, self.setting)
        exported = gpd.read_file(
            distribution.OUTPUT_CSV.parent /
            f"A05_Region-stats_test_{distribution.VERSION}.shp"
        )
        self.assertEqual(len(exported), 2)
        self.assertEqual(exported.CoralCount.tolist(), [2, 2])
        self.assertEqual(exported.CoralKm2.tolist(), [0.0002, 0.0002])
        self.assertTrue(exported.geometry.iloc[1].equals(regions.geometry.iloc[1]))

    def test_capad_overlaps_composite_identity_and_no_match(self):
        reefs = gpd.GeoDataFrame({
            "CountFID": [1], "RB_Type_L2": ["Coral Reef"],
            "geometry": [box(0, 0, 100, 40)],
        }, crs=3577)
        regions = gpd.GeoDataFrame({
            "TYPE": ["Federal", "State", "State"],
            "NAME": ["Shared", "Shared", "Thin"],
            "geometry": [box(0, 0, 60, 40), box(40, 0, 80, 40),
                         box(98, 0, 100, 40)],
        }, crs=3577)
        portions = self.slice_and_assign(reefs, regions, self.capad)
        self.assertEqual(len(portions), 4)
        kept = portions[portions.Sliver == 0]
        areas = kept.set_index(["TYPE", "NAME"]).Area_km2.to_dict()
        self.assertEqual(areas, {("Federal", "Shared"): 0.0024,
                                 ("State", "Shared"): 0.0016,
                                 ("", "No match"): 0.00072})
        self.assertTrue(portions.geometry.iloc[2].equals(box(80, 0, 98, 40)) or
                        any(geometry.equals(box(80, 0, 98, 40))
                            for geometry in portions.geometry))
        cached = self.slice_and_assign(reefs, regions, self.capad)
        self.assertEqual(len(cached), 4)
        self.assertEqual(cached.loc[cached.NAME == "No match", "TYPE"].iloc[0], "")
        checks = distribution.check_conservation(cached, reefs, self.capad["name"])
        self.assertEqual([row["Status"] for row in checks], ["Pass", "Pass"])

        records = distribution.summarise([(self.capad["name"], cached)])
        self.assertEqual([(row["Region_type"], row["Region_name"],
                   row["Coral_reef_count"], row["Coral_reef_partial_count"])
                  for row in records],
                 [("Federal", "Shared", 1, 0), ("State", "Shared", 0, 1),
                  ("", "No match", 0, 1)])
        with distribution.OUTPUT_CSV.open(newline="", encoding="utf-8") as output:
            csv_rows = list(csv.DictReader(output))
        self.assertEqual(csv_rows[0]["Coral_reef_area_km2"], "0.002400")
        distribution.export_region_stats(regions, None, records, self.capad)
        exported = gpd.read_file(
            distribution.OUTPUT_CSV.parent /
            f"A05_Region-stats_capad_{distribution.VERSION}.shp"
        )
        self.assertEqual(set(zip(exported.TYPE, exported.NAME)),
                         {("Federal", "Shared"), ("State", "Shared")})
        self.assertEqual(exported.CoralCount.tolist(), [1, 0])
        self.assertEqual(exported.CoralPart.tolist(), [0, 1])
        self.assertEqual(exported.CoralKm2.tolist(), [0.0024, 0.0016])

    def test_capad_dissolves_zones_by_type_and_name(self):
        source = Path(self.directory.name) / "source.shp"
        gpd.GeoDataFrame({
            "TYPE": ["Federal", "Federal", "State"],
            "NAME": ["Shared", "Shared", "Shared"],
            "geometry": [box(0, 0, 20, 20), box(10, 0, 30, 20),
                         box(0, 0, 30, 20)],
        }, crs=3577).to_file(source)
        regions = distribution.load_capad(dict(self.capad, source=source))
        self.assertEqual(len(regions), 2)
        self.assertEqual(set(zip(regions.TYPE, regions.NAME)),
                         {("Federal", "Shared"), ("State", "Shared")})
        self.assertTrue(regions.geometry.is_valid.all())
        self.assertTrue(all(geometry.hausdorff_distance(box(0, 0, 30, 20)) <= 10
                    for geometry in regions.geometry))

    def test_capad_repairs_invalid_source_geometry(self):
        source = Path(self.directory.name) / "invalid.shp"
        gpd.GeoDataFrame({
            "TYPE": ["Federal"], "NAME": ["Crossing"],
            "geometry": [Polygon([(0, 0), (20, 20), (0, 20), (20, 0), (0, 0)])],
        }, crs=3577).to_file(source)
        regions = distribution.load_capad(dict(self.capad, source=source))
        self.assertEqual(len(regions), 1)
        self.assertTrue(regions.geometry.is_valid.all())
        self.assertAlmostEqual(regions.geometry.iloc[0].area, 200)

    def test_capad_simplifies_jagged_boundary_within_tolerance(self):
        source = Path(self.directory.name) / "jagged.shp"
        boundary = [(100 - x, 100 + (3 if x % 10 else 0))
                    for x in range(0, 101, 5)]
        original = Polygon([(0, 0), (100, 0)] + boundary)
        gpd.GeoDataFrame({
            "TYPE": ["Federal"], "NAME": ["Jagged"], "geometry": [original],
        }, crs=3577).to_file(source)
        setting = dict(self.capad, source=source)
        simplified = distribution.load_capad(setting).geometry.iloc[0]
        cached = distribution.load_capad(setting).geometry.iloc[0]
        self.assertLess(len(simplified.exterior.coords), len(original.exterior.coords))
        self.assertLessEqual(simplified.hausdorff_distance(original),
                             setting["simplify_m"])
        self.assertTrue(simplified.is_valid)
        self.assertTrue(cached.equals(simplified))

    def test_capad_keeps_original_if_simplification_is_invalid(self):
        source = Path(self.directory.name) / "valid.shp"
        original = box(0, 0, 100, 100)
        gpd.GeoDataFrame({
            "TYPE": ["Federal"], "NAME": ["Reserve"], "geometry": [original],
        }, crs=3577).to_file(source)
        bowtie = Polygon([(0, 0), (20, 20), (0, 20), (20, 0), (0, 0)])
        with patch.object(gpd.GeoSeries, "simplify",
                          return_value=gpd.GeoSeries([bowtie], crs=3577)):
            regions = distribution.load_capad(dict(self.capad, source=source))
        self.assertTrue(regions.geometry.iloc[0].equals(original))

    def test_material_overlap_aborts_with_debug_shapefile(self):
        regions = gpd.GeoDataFrame({
            "TYPE": ["", ""], "NAME": ["A", "B"],
            "geometry": [box(0, 0, 20, 20), box(14, 0, 30, 20)],
        }, crs=3577)
        with self.assertRaisesRegex(ValueError, "overlaps wider than 5 m"):
            distribution.check_overlaps(regions, "test")
        self.assertTrue((distribution.WORK_DIR / "debug-overlap-test.shp").exists())


if __name__ == "__main__":
    unittest.main()