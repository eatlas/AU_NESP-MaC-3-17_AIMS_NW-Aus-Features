"""Checks for full-dataset attribute counts and honest denominators."""

import importlib.util
from pathlib import Path
import unittest

import pandas as pd


SCRIPT = Path(__file__).resolve().parents[1] / "A08-attribute-summary.py"
spec = importlib.util.spec_from_file_location("attribute_summary", SCRIPT)
attributes = importlib.util.module_from_spec(spec)
spec.loader.exec_module(attributes)


class AttributeSummaryTests(unittest.TestCase):
    def setUp(self):
        self.features = pd.DataFrame({
            "RB_Type_L2": ["Coral Reef", "Rocky Reef", "Sediment", "Other"],
            "DepthCat": [" Deep ", "Intertidal", "Shallow", "Land"],
            "FeatConf": ["High", "Low", None, " "],
            "TypeConf": ["Medium", "High", "Very Low", "Very High"],
        })

    def test_all_types_count_once_per_attribute(self):
        summary = attributes.summarise_attributes(self.features)
        for attribute in attributes.ATTRIBUTES:
            selected = summary[summary.Attribute == attribute]
            self.assertEqual(selected.Feature_count.sum(), 4)
            self.assertAlmostEqual(selected.Percent_of_all_features.sum(), 100)
        depth = summary[summary.Attribute == "DepthCat"].set_index("Category")
        self.assertEqual(depth.loc["Land", "Feature_count"], 1)
        self.assertEqual(depth.loc["Deep", "Feature_count"], 1)
        self.assertNotIn("Region", summary.columns)
        self.assertNotIn("Area_km2", summary.columns)

    def test_missing_categories_stay_in_denominator(self):
        summary = attributes.summarise_attributes(self.features)
        confidence = summary[summary.Attribute == "FeatConf"].set_index("Category")
        self.assertEqual(confidence.loc["Unassigned", "Feature_count"], 2)
        self.assertEqual(confidence.loc["High", "Percent_of_all_features"], 25)

    def test_unused_categories_omitted_but_zero_unassigned_retained(self):
        summary = attributes.summarise_attributes(self.features)
        depth = summary[summary.Attribute == "DepthCat"].set_index("Category")
        self.assertNotIn("Surface", depth.index)
        self.assertEqual(depth.loc["Unassigned", "Feature_count"], 0)
        confidence = summary[summary.Attribute == "FeatConf"].set_index("Category")
        self.assertNotIn("Very High", confidence.index)
        table = attributes.report_tables(summary, "test")
        self.assertNotIn("| Surface |", table)
        self.assertIn("| Unassigned | 0 | 0.0 |", table)

    def test_additional_category_retained_without_relabelling(self):
        self.features.loc[0, "TypeConf"] = "Future category"
        summary = attributes.summarise_attributes(self.features)
        extra = summary[(summary.Attribute == "TypeConf") &
                        (summary.Category == "Future category")]
        self.assertEqual(extra.Feature_count.iloc[0], 1)

    def test_report_contains_three_tables_and_limitations(self):
        table = attributes.report_tables(attributes.summarise_attributes(self.features), "test")
        self.assertEqual(table.count("**Table A08-"), 3)
        self.assertIn("A08-attribute-summary.py", table)
        self.assertIn("not countable reefs", table)
        self.assertIn("not independently validated", table)

    def test_empty_or_missing_input_rejected(self):
        with self.assertRaisesRegex(ValueError, "empty"):
            attributes.summarise_attributes(self.features.iloc[:0])
        with self.assertRaisesRegex(ValueError, "Missing attribute columns"):
            attributes.summarise_attributes(self.features.drop(columns="FeatConf"))


if __name__ == "__main__":
    unittest.main()