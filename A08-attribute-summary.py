"""Describe depth and confidence attributes of every published L3 feature.

See A08-attribute-summary-spec.md for interpretation and limitations.
"""

import configparser
from pathlib import Path

import geopandas as gpd
import pandas as pd


ROOT = Path(__file__).resolve().parent
config = configparser.ConfigParser()
config.read(ROOT / "config.ini")
VERSION = config.get("general", "version")
DATA_DIR = ROOT / "data" / VERSION
L3_DATASET = (DATA_DIR / "out" / "full-classes" /
              f"AU_NESP-MaC-3-17_AIMS_NW-Aus-Features_L3_{VERSION}.shp")
OUTPUT_DIR = DATA_DIR / "out" / "stats"
OUTPUT_CSV = OUTPUT_DIR / f"A08_Attribute-summary_{VERSION}.csv"
OUTPUT_MD = OUTPUT_DIR / f"A08_Attribute-summary_{VERSION}.md"
ATTRIBUTES = {
    "DepthCat": ("Land", "Surface", "Intertidal", "Very Shallow", "Shallow", "Deep"),
    "FeatConf": ("Very Low", "Low", "Medium", "High", "Very High"),
    "TypeConf": ("Very Low", "Low", "Medium", "High", "Very High"),
}
MISSING = "Unassigned"
DESCRIPTIONS = {
    "DepthCat": "Recorded depth category of mapped features",
    "FeatConf": "Recorded confidence that mapped features are genuine features",
    "TypeConf": "Recorded confidence in the assigned feature classification",
}


def summarise_attributes(features):
    """Count every record once per attribute, retaining missing and novel values."""
    missing = set(ATTRIBUTES) - set(features.columns)
    if missing:
        raise ValueError(f"Missing attribute columns: {sorted(missing)}")
    if features.empty:
        raise ValueError("Published feature dataset is empty")
    total = len(features)
    rows = []
    for attribute, preferred in ATTRIBUTES.items():
        values = features[attribute].astype("string").str.strip()
        values = values.mask(values.isna() | values.eq(""), MISSING)
        counts = values.value_counts()
        extras = sorted(set(counts.index) - set(preferred) - {MISSING})
        if extras:
            print(f"Additional recorded {attribute} categories retained: {extras}")
        categories = (*preferred, *extras, MISSING)
        for category in categories:
            count = int(counts.get(category, 0))
            if count == 0 and category != MISSING:
                continue
            rows.append({"Attribute": attribute, "Category": category,
                         "Feature_count": count, "Percent_of_all_features": 100 * count / total})
        if sum(int(counts.get(category, 0)) for category in categories) != total:
            raise ValueError(f"Category counts do not reconcile for {attribute}")
    return pd.DataFrame(rows)


def report_tables(summary, version):
    """Create a compact appendix overview with one table per attribute."""
    total = int(summary.loc[summary.Attribute == "DepthCat", "Feature_count"].sum())
    lines = ["# Overview of dataset attributes", "",
             f"These tables describe the recorded attributes of all {total:,} published "
             f"L3 features in dataset {version}, across its full geographic extent and "
             "all feature types. Each polygon record counts once in each table. "
             "These are mapped-feature counts, not countable reefs. No regional "
             "filter or area weighting is applied. Analysis: A08-attribute-summary.py.", ""]
    for index, (attribute, description) in enumerate(DESCRIPTIONS.items(), start=1):
        lines.extend([f"**Table A08-{index}.** {description} ({attribute}). "
                      "Percentages use all published features, including unassigned values.", "",
                      "| Recorded category | Features | % of all features |",
                      "| :--- | ---: | ---: |"])
        selected = summary[summary.Attribute == attribute]
        for row in selected.itertuples():
            lines.append(f"| {row.Category} | {row.Feature_count:,} | "
                         f"{row.Percent_of_all_features:.1f} |")
        lines.extend([f"| **Total** | **{total:,}** | **100.0** |", ""])
    lines.extend([
        "## Interpretation", "",
        "DepthCat describes the shallowest representative portion or peak of a "
        "feature, not the depth throughout it. This portion may represent only "
        "5-10% of its area. A feature with an intertidal peak may extend into much "
        "deeper water. Only categories recorded in the dataset are shown, apart "
        "from Unassigned, which is always retained. These counts describe the dataset, not regional habitat "
        "depth distributions or the proportion of reefs detected at each depth.", "",
        "The coarse depth categories support Parks Australia's Natural Values "
        "Common Language (NVCL). Intertidal indicates exposure at low tide. Very "
        "Shallow uses a nominal threshold near 2.5 m below Lowest Astronomical "
        "Tide (LAT). Shallow and Deep use spectral visibility informed by the "
        "Coral Sea calibration, where green-band peak detection was approximately "
        "25 m LAT, intended to approximate the NVCL 30 m shallow/mesophotic "
        "division. Most depths were estimated from satellite imagery. These "
        "thresholds have not been calibrated to local water conditions throughout "
        "this dataset. Turbidity, substrate reflectance, tides and image quality "
        "affect detection. Few recorded Deep features do not demonstrate that "
        "deep reefs are scarce.", "",
        "FeatConf records the digitiser's confidence that a feature is genuine, "
        "rather than an image artefact or misinterpretation. TypeConf records "
        "confidence that its classification is correct. A genuine feature can "
        "have an uncertain type. These are expert-assigned categories, not "
        "independently validated probabilities, accuracy scores or estimates "
        "of mapping completeness. The same category label has different meaning "
        "for the two attributes.", "",
        "Each small feature has the same weight as a large complex. Splitting "
        "a reef into several L3 features changes these distributions without "
        "adding a new reef. Full-extent results include offshore islands, "
        "shelf-edge features and partial Timor/Indonesian coverage. They must "
        "not be presented as representative regional samples.", "",
        "Unassigned retains null and blank values. Publication processing defaults "
        "missing input DepthCat values to Shallow, so zero Unassigned features "
        "does not establish that every depth category was independently assessed. "
        "Percentages may not sum exactly after rounding.", "",
        "Depth-area distributions and bathymetry consistency checks belong to the "
        "subsequent national dataset workflow, which combines mapping sources and "
        "extracts available bathymetry for each reef. They are not reproduced here.",
    ])
    return "\n".join(lines) + "\n"


def main():
    features = gpd.read_file(L3_DATASET, ignore_geometry=True)
    summary = summarise_attributes(features)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summary.to_csv(OUTPUT_CSV, index=False, float_format="%.6f")
    OUTPUT_MD.write_text(report_tables(summary, VERSION), encoding="utf-8")
    print(f"Summarised all {len(features):,} published L3 features")
    print(f"Wrote attribute statistics: {OUTPUT_CSV}")
    print(f"Wrote appendix tables: {OUTPUT_MD}")


if __name__ == "__main__":
    main()