"""Count and measure countable reefs in three independent regionalisations.

Intermediate shapefiles are caches. Delete a stage's shapefile (and its
sidecars) to rebuild it after changing its input or processing rules.
"""

import configparser
import csv
from pathlib import Path

import geopandas as gpd
from shapely.geometry import MultiPolygon, Polygon
from shapely.ops import unary_union
from shapely.validation import make_valid

from reef_utils import cluster_countable


ROOT = Path(__file__).resolve().parent
config = configparser.ConfigParser()
config.read(ROOT / "config.ini")
VERSION = config.get("general", "version")
DATA_DIR = ROOT / "data" / VERSION
WORK_DIR = ROOT / "working" / VERSION / "A05"
INPUT_REEFS = (DATA_DIR / "out" / "simp-classes" /
               f"AU_NESP-MaC-3-17_AIMS_NW-Aus-Features_L2_{VERSION}.shp")
COUNTABLE_CACHE = WORK_DIR / "countable-reefs.shp"
OUTPUT_CSV = (DATA_DIR / "out" / "stats" /
              f"NW-Aus-Features_Region-stats_{VERSION}.csv")

AREA_CRS = 3112
CAPAD_SIMPLIFY_M = 10.0
CHECK_REGION_OVERLAPS = True
SLIVER_BUFFER_M = 5.0
OVERLAP_BUFFER_M = 2.5
NO_MATCH = "No match"
REEF_TYPES = ("Coral Reef", "Rocky Reef")
REGIONS = (
    ("IMCRA v4.0 Meso-scale Bioregions (2023)",
     DATA_DIR / "in-3p" / "IMCRA-v4-0-Meso-Bioregions" /
     "IMCRA-v4-Mesoscale-Bioregions.shp", "MESO_NAME", "imcra"),
    ("Analysis-regions v1",
     DATA_DIR / "in-3p" / "nesp-3-17-analysis-regions" /
     "analysis-regions.shp", "subregion", "analysis-region"),
)
CAPAD_NAME = "CAPAD 2024 - Marine"
CAPAD_SOURCE = (DATA_DIR / "in-3p" / "CAPAD-2024" /
                "Collaborative_Australian_Protected_Areas_Database_(CAPAD)_2024_-_Marine.shp")


def polygons(geometry):
    """Keep polygonal parts of an overlay result, discarding lines and points."""
    if geometry.is_empty:
        return Polygon()
    if isinstance(geometry, (Polygon, MultiPolygon)):
        return geometry
    if not hasattr(geometry, "geoms"):
        return Polygon()
    parts = [part for part in geometry.geoms
             if isinstance(part, (Polygon, MultiPolygon)) and not part.is_empty]
    return unary_union(parts) if parts else Polygon()


def load_countable():
    """Cluster coral and rocky reefs once, then cache their stable CountFIDs."""
    if COUNTABLE_CACHE.exists():
        print(f"Loading countable reefs: {COUNTABLE_CACHE}", flush=True)
        return gpd.read_file(COUNTABLE_CACHE).to_crs(AREA_CRS)

    print(f"Loading reef features: {INPUT_REEFS}", flush=True)
    reefs = gpd.read_file(INPUT_REEFS)[["RB_Type_L2", "geometry"]]
    reefs = reefs[reefs["RB_Type_L2"].isin(REEF_TYPES)].to_crs(AREA_CRS)
    print(f"Clustering {len(reefs)} reef features", flush=True)
    countable, stats = cluster_countable(reefs, show_progress=True)
    if stats["n_unassigned"]:
        raise ValueError(f"{stats['n_unassigned']} reefs could not be clustered")
    countable = countable.reset_index(drop=True)
    countable["CountFID"] = countable.index + 1
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    countable.to_file(COUNTABLE_CACHE)
    print(f"Cached {len(countable)} countable reefs: {COUNTABLE_CACHE}", flush=True)
    return countable


def load_regions(source, field, slug):
    """Load named non-overlapping regions in EPSG:3112."""
    cache = WORK_DIR / f"regions-{slug}.shp"
    if cache.exists():
        print(f"Loading cached {slug} regions: {cache}", flush=True)
        return gpd.read_file(cache).to_crs(AREA_CRS)

    print(f"Loading {slug} regions: {source}", flush=True)
    regions = gpd.read_file(source)[[field, "geometry"]].to_crs(AREA_CRS)
    if regions[field].isna().any() or regions[field].eq(NO_MATCH).any():
        raise ValueError(f"Missing or reserved region name in {source}")
    if regions.geometry.isna().any() or not regions.geometry.is_valid.all():
        raise ValueError(f"Null or invalid region geometry in {source}")
    regions = regions.rename(columns={field: "RegionName"})
    regions = regions[["RegionName", "geometry"]].reset_index(drop=True)
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    regions.to_file(cache)
    print(f"Cached {len(regions)} regions: {cache}", flush=True)
    return regions


def load_capad():
    """Dissolve CAPAD by TYPE and NAME, then simplify in metres."""
    cache = WORK_DIR / f"regions-capad-{CAPAD_SIMPLIFY_M:g}m.shp"
    if cache.exists():
        print(f"Loading cached CAPAD regions: {cache}", flush=True)
        return gpd.read_file(cache).to_crs(AREA_CRS)

    print(f"Loading CAPAD regions: {CAPAD_SOURCE}", flush=True)
    regions = gpd.read_file(CAPAD_SOURCE)[["TYPE", "NAME", "geometry"]].to_crs(AREA_CRS)
    if (regions[["TYPE", "NAME"]].isna().any().any() or
            regions["NAME"].eq(NO_MATCH).any()):
        raise ValueError(f"Missing or reserved CAPAD identity in {CAPAD_SOURCE}")
    if regions.geometry.isna().any():
        raise ValueError(f"Null CAPAD geometry in {CAPAD_SOURCE}")
    invalid = ~regions.geometry.is_valid
    if invalid.any():
        print(f"Repairing {invalid.sum()} invalid CAPAD geometries", flush=True)
        regions.loc[invalid, "geometry"] = regions.loc[invalid, "geometry"].apply(
            lambda geometry: polygons(make_valid(geometry)))
    if regions.geometry.is_empty.any() or not regions.geometry.is_valid.all():
        raise ValueError(f"Unrepairable CAPAD geometry in {CAPAD_SOURCE}")
    print(f"Dissolving {len(regions)} CAPAD zones by TYPE and NAME", flush=True)
    regions = regions.dissolve(by=["TYPE", "NAME"], as_index=False)
    regions = regions[["TYPE", "NAME", "geometry"]].reset_index(drop=True)
    original = regions.geometry.copy()
    print(f"Simplifying {len(regions)} CAPAD areas to {CAPAD_SIMPLIFY_M:g} m", flush=True)
    regions["geometry"] = regions.geometry.simplify(CAPAD_SIMPLIFY_M,
                                                   preserve_topology=True)
    invalid = regions.geometry.is_empty | ~regions.geometry.is_valid
    if invalid.any():
        print(f"Retaining original boundaries for {invalid.sum()} CAPAD areas "
              "whose simplified geometry is invalid", flush=True)
        regions.loc[invalid, "geometry"] = original.loc[invalid]
    if regions.geometry.is_empty.any() or not regions.geometry.is_valid.all():
        raise ValueError("CAPAD has empty or invalid dissolved geometry")
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    regions.to_file(cache)
    print(f"Cached {len(regions)} CAPAD protected areas: {cache}", flush=True)
    return regions


def check_overlaps(regions, slug):
    """Save and reject overlaps surviving a 2.5 m inward buffer."""
    pairs = regions.sindex.query(regions.geometry, predicate="intersects")
    overlaps = []
    for first, second in zip(*pairs):
        if first >= second:
            continue
        intersection = polygons(regions.geometry.iloc[first].intersection(
            regions.geometry.iloc[second]))
        if not intersection.is_empty and not intersection.buffer(-OVERLAP_BUFFER_M).is_empty:
            overlaps.append({"RegionA": regions["RegionName"].iloc[first],
                             "RegionB": regions["RegionName"].iloc[second],
                             "geometry": intersection})
    if overlaps:
        path = WORK_DIR / f"debug-overlap-{slug}.shp"
        gpd.GeoDataFrame(overlaps, crs=regions.crs).to_file(path)
        raise ValueError(f"{len(overlaps)} region overlaps wider than 5 m; inspect {path}")


def slice_reefs(reefs, regions, slug):
    """Allocate each countable reef's area to regions or No match and cache it."""
    cache = WORK_DIR / f"reefs-by-{slug}.shp"
    if cache.exists():
        print(f"Loading reef portions: {cache}", flush=True)
        return gpd.read_file(cache).to_crs(AREA_CRS)

    print(f"Slicing {len(reefs)} countable reefs by {slug} regions", flush=True)
    rows = []
    removed_area = 0.0
    input_area = 0.0
    for position, reef in enumerate(reefs.itertuples(index=False), start=1):
        remaining = reef.geometry
        input_area += remaining.area
        by_name = {}
        # Remove each assigned piece so adjacent or near-overlapping regions
        # cannot claim the same reef area twice.
        for region_index in regions.sindex.query(remaining, predicate="intersects"):
            region = regions.iloc[region_index]
            piece = polygons(remaining.intersection(region.geometry))
            if piece.is_empty:
                continue
            by_name.setdefault(region.RegionName, []).append(piece)
            remaining = polygons(remaining.difference(region.geometry))
            if remaining.is_empty:
                break
        if not remaining.is_empty:
            by_name.setdefault(NO_MATCH, []).append(remaining)

        # Merge pieces by name before testing for slivers and counting the reef.
        for name, pieces in by_name.items():
            piece = polygons(unary_union(pieces))
            if piece.buffer(-SLIVER_BUFFER_M).is_empty:
                removed_area += piece.area
                continue
            rows.append({"CountFID": reef.CountFID, "RB_Type_L2": reef.RB_Type_L2,
                         "RegionName": name, "Area_km2": piece.area / 1e6,
                         "geometry": piece})
        if position % 1000 == 0:
            print(f"  {slug}: {position}/{len(reefs)} reefs", flush=True)

    result = gpd.GeoDataFrame(rows, columns=["CountFID", "RB_Type_L2",
                                            "RegionName", "Area_km2", "geometry"],
                              crs=AREA_CRS)
    # Account for discarded slivers when comparing allocated and input area.
    accounted_area = sum(row["Area_km2"] for row in rows) * 1e6 + removed_area
    tolerance = max(1.0, input_area * 1e-8)
    if abs(input_area - accounted_area) > tolerance:
        raise ValueError(f"{slug}: area mismatch of {input_area - accounted_area:.2f} m2")
    print(f"{slug}: {len(result)} portions; slivers removed: "
          f"{removed_area / 1e6:.6f} km2; area reconciled within "
          f"{tolerance:.2f} m2", flush=True)
    result.to_file(cache)
    return result


def slice_capad(reefs, regions):
    """Intersect each reef with every CAPAD area; derive No match from their union."""
    cache = WORK_DIR / f"reefs-by-capad-{CAPAD_SIMPLIFY_M:g}m.shp"
    if cache.exists():
        print(f"Loading reef portions: {cache}", flush=True)
        portions = gpd.read_file(cache).to_crs(AREA_CRS)
        portions.loc[portions["NAME"] == NO_MATCH, "TYPE"] = ""
        return portions

    print(f"Slicing {len(reefs)} countable reefs by CAPAD protected areas", flush=True)
    rows = []
    input_area = 0.0
    kept_union_area = 0.0
    kept_outside_area = 0.0
    removed_union_area = 0.0
    removed_outside_area = 0.0
    for position, reef in enumerate(reefs.itertuples(index=False), start=1):
        input_area += reef.geometry.area
        covered = []
        for region_index in regions.sindex.query(reef.geometry, predicate="intersects"):
            region = regions.iloc[region_index]
            piece = polygons(reef.geometry.intersection(region.geometry))
            if piece.is_empty:
                continue
            covered.append(piece)
            if piece.buffer(-SLIVER_BUFFER_M).is_empty:
                continue
            rows.append({"CountFID": reef.CountFID, "RB_Type_L2": reef.RB_Type_L2,
                         "TYPE": region.TYPE, "NAME": region.NAME,
                         "Area_km2": piece.area / 1e6, "geometry": piece})

        # Union the intersections before subtracting, so overlaps count only
        # once when determining the outside portion and checking area balance.
        inside = unary_union(covered) if covered else Polygon()
        if inside.buffer(-SLIVER_BUFFER_M).is_empty:
            removed_union_area += inside.area
        else:
            kept_union_area += inside.area
        outside = polygons(reef.geometry.difference(inside))
        if outside.buffer(-SLIVER_BUFFER_M).is_empty:
            removed_outside_area += outside.area
        else:
            kept_outside_area += outside.area
            rows.append({"CountFID": reef.CountFID, "RB_Type_L2": reef.RB_Type_L2,
                         "TYPE": "", "NAME": NO_MATCH,
                         "Area_km2": outside.area / 1e6, "geometry": outside})
        if position % 1000 == 0:
            print(f"  capad: {position}/{len(reefs)} reefs", flush=True)

    tolerance = max(1.0, input_area * 1e-8)
    accounted_area = (kept_union_area + kept_outside_area +
                      removed_union_area + removed_outside_area)
    if abs(input_area - accounted_area) > tolerance:
        raise ValueError("CAPAD: union-based inside and outside areas do not reconcile")
    result = gpd.GeoDataFrame(rows, columns=["CountFID", "RB_Type_L2", "TYPE",
                                            "NAME", "Area_km2", "geometry"],
                              crs=AREA_CRS)
    print(f"capad: {len(result)} portions; union-based slivers removed: "
          f"{(removed_union_area + removed_outside_area) / 1e6:.6f} km2; "
          f"area reconciled within {tolerance:.2f} m2", flush=True)
    result.to_file(cache)
    return result


def summarise(datasets):
    """Write counts of distinct reefs and clipped areas for occupied regions."""
    records = []
    for dataset_name, portions in datasets:
        if dataset_name != CAPAD_NAME:
            portions = portions.assign(TYPE="", NAME=portions["RegionName"])
        grouped = (portions.groupby(["TYPE", "NAME", "RB_Type_L2"])
                   .agg(count=("CountFID", "nunique"), area=("Area_km2", "sum")))
        for region_type, name in portions[["TYPE", "NAME"]].drop_duplicates().itertuples(index=False):
            coral_key = (region_type, name, "Coral Reef")
            rocky_key = (region_type, name, "Rocky Reef")
            coral = grouped.loc[coral_key] if coral_key in grouped.index else None
            rocky = grouped.loc[rocky_key] if rocky_key in grouped.index else None
            coral_count = int(coral["count"]) if coral is not None else 0
            rocky_count = int(rocky["count"]) if rocky is not None else 0
            if coral_count + rocky_count:
                records.append((dataset_name, region_type, name, coral_count,
                                f"{coral['area'] if coral is not None else 0:.6f}",
                                rocky_count,
                                f"{rocky['area'] if rocky is not None else 0:.6f}"))
    records.sort(key=lambda row: (row[0], row[2] == NO_MATCH, row[1], row[2]))
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_CSV.open("w", newline="", encoding="utf-8") as output:
        writer = csv.writer(output)
        writer.writerow(["Region_dataset", "Region_type", "Region_name", "Coral_reef_count",
                         "Coral_reef_area_km2", "Rocky_reef_count",
                         "Rocky_reef_area_km2"])
        writer.writerows(records)
    print(f"Wrote {len(records)} region summaries: {OUTPUT_CSV}", flush=True)
    return records


def export_region_stats(regions, records, dataset_name, slug):
    """Attach CSV totals to occupied source regions for mapping."""
    stats = {(row[1], row[2]): row for row in records
             if row[0] == dataset_name and row[2] != NO_MATCH}
    if dataset_name == CAPAD_NAME:
        keys = list(zip(regions["TYPE"], regions["NAME"]))
    else:
        keys = [("", name) for name in regions["RegionName"]]
    mapped = regions.loc[[key in stats for key in keys]].copy()
    matching = [stats[key] for key in keys if key in stats]
    mapped["CoralCount"] = [row[3] for row in matching]
    mapped["CoralKm2"] = [float(row[4]) for row in matching]
    mapped["RockyCount"] = [row[5] for row in matching]
    mapped["RockyKm2"] = [float(row[6]) for row in matching]
    path = OUTPUT_CSV.parent / f"NW-Aus-Features_Region-stats_{slug}_{VERSION}.shp"
    mapped.to_file(path)
    print(f"Wrote {len(mapped)} occupied {slug} regions: {path}", flush=True)


def main():
    """Run each regionalisation independently against the same countable reefs."""
    reefs = load_countable()
    datasets = []
    region_layers = []
    for name, source, field, slug in REGIONS:
        print(f"Processing {name}", flush=True)
        regions = load_regions(source, field, slug)
        if CHECK_REGION_OVERLAPS:
            print(f"Checking {len(regions)} {slug} regions for overlaps", flush=True)
            check_overlaps(regions, slug)
        datasets.append((name, slice_reefs(reefs, regions, slug)))
        region_layers.append(regions)
    print(f"Processing {CAPAD_NAME}", flush=True)
    capad = load_capad()
    datasets.append((CAPAD_NAME, slice_capad(reefs, capad)))
    records = summarise(datasets)
    for (name, _, _, slug), regions in zip(REGIONS, region_layers):
        export_region_stats(regions, records, name, slug)
    export_region_stats(capad, records, CAPAD_NAME, "capad")


if __name__ == "__main__":
    main()