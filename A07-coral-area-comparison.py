"""Compare L3 coral reef boundary area with UQ Coral/Algae benthic area.

Run 01a-download-input-data.py to obtain the published habitat statistics CSV.
The calculation uses all L3 Coral Reef polygons, not A05 countable reefs.
"""

import configparser
import csv
import math
from pathlib import Path

import geopandas as gpd


ROOT = Path(__file__).resolve().parent
config = configparser.ConfigParser()
config.read(ROOT / "config.ini")
VERSION = config.get("general", "version")
DATA_DIR = ROOT / "data" / VERSION
L3_DATASET = (DATA_DIR / "out" / "full-classes" /
              f"AU_NESP-MaC-3-17_AIMS_NW-Aus-Features_L3_{VERSION}.shp")
REGIONS = DATA_DIR / "in-3p" / "nesp-3-17-analysis-regions" / "analysis-regions.shp"
HABITAT_CSV = DATA_DIR / "in-3p" / "UQ-shallow-habitat" / "A02_Habitat-area-stats.csv"
OUTPUT_DIR = DATA_DIR / "out" / "stats"
OUTPUT_CSV = OUTPUT_DIR / f"A07_Coral-area-comparison_{VERSION}.csv"
OUTPUT_MD = OUTPUT_DIR / f"A07_Coral-area-comparison_{VERSION}.md"

SUBREGIONS = (
    "North (Nearshore)", "North (Offshore)",
    "North-west (Nearshore)", "North-west (Offshore)",
    "South-west (Nearshore)", "South-west (Offshore)",
)
HEADER = ("Region", "Habitat mapping: Coral/Algae area km2",
          "Boundary mapping: Coral Reef km2")
DESCRIPTION = (
    "Area of `Coral/Algae` in the UQ benthic habitat classification compared with "
    "area classified as `RB_Type_L3 = Coral Reef` in the AIMS reef boundary "
    "mapping, within the North, North-west and South-west Analysis-regions v1 "
    "subregions. The reef boundary mapping roughly separates actively growing "
    "coral reef areas (`Coral Reef`) from `Coral Reef Flat`, which is excluded "
    "here. These classes are broadly, but not exactly, comparable: "
    "`Coral/Algae` may also include algae on rocky reefs, and the benthic "
    "mapping does not extend as deep as the reef boundary mapping."
)


def habitat_areas(path):
    """Require one published benthic Coral/Algae area for each subregion."""
    required = {"Regionalisation", "Region_name", "Mapping", "Class_id",
                "Class_name", "Area_km2"}
    areas = {}
    with path.open(newline="", encoding="utf-8-sig") as source:
        reader = csv.DictReader(source)
        missing_columns = required - set(reader.fieldnames or [])
        if missing_columns:
            raise ValueError(f"Missing habitat columns: {sorted(missing_columns)}")
        for row in reader:
            if (row["Regionalisation"] != "Analysis-regions v1" or
                    row["Mapping"] != "Benthic" or row["Class_id"] != "15" or
                    row["Class_name"] != "Coral/Algae" or
                    row["Region_name"] not in SUBREGIONS):
                continue
            name = row["Region_name"]
            if name in areas:
                raise ValueError(f"Duplicate habitat area for {name}")
            area = float(row["Area_km2"])
            if not math.isfinite(area) or area < 0:
                raise ValueError(f"Invalid habitat area for {name}: {area}")
            areas[name] = area
    missing = set(SUBREGIONS) - areas.keys()
    if missing:
        raise ValueError(f"Missing habitat areas for: {sorted(missing)}")
    return areas


def boundary_areas(reef_path, region_path):
    """Clip all L3 Coral Reef geometries to each subregion in EPSG:3577."""
    regions = gpd.read_file(region_path)
    if "subregion" not in regions.columns:
        raise ValueError("Analysis-regions shapefile has no subregion field")
    regions = regions[regions["subregion"].isin(SUBREGIONS)].to_crs(3577)
    counts = regions["subregion"].value_counts()
    if set(counts.index) != set(SUBREGIONS) or (counts != 1).any():
        raise ValueError(f"Expected one polygon per subregion; found {counts.to_dict()}")

    reefs = gpd.read_file(reef_path)
    if "RB_Type_L3" not in reefs.columns:
        raise ValueError("L3 boundary shapefile has no RB_Type_L3 field")
    reefs = reefs[reefs["RB_Type_L3"] == "Coral Reef"].to_crs(3577)
    areas = {}
    for name in SUBREGIONS:
        boundary = regions.loc[regions["subregion"] == name, "geometry"].iloc[0]
        candidates = reefs.iloc[reefs.sindex.query(boundary, predicate="intersects")]
        areas[name] = candidates.geometry.intersection(boundary).area.sum() / 1e6
    return areas


def main():
    habitat = habitat_areas(HABITAT_CSV)
    boundary = boundary_areas(L3_DATASET, REGIONS)
    rows = [(name, f"{habitat[name]:.1f}", f"{boundary[name]:.1f}")
            for name in SUBREGIONS]

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with OUTPUT_CSV.open("w", newline="", encoding="utf-8") as output:
        writer = csv.writer(output)
        writer.writerow(HEADER)
        writer.writerows(rows)

    lines = [DESCRIPTION, "", "| " + " | ".join(HEADER) + " |",
             "| :--- | ---: | ---: |"]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    OUTPUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {len(rows)} comparison rows: {OUTPUT_CSV} and {OUTPUT_MD}")


if __name__ == "__main__":
    main()