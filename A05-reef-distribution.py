"""Count and measure countable reefs in three independent regionalisations.

Intermediate shapefiles are caches. Delete a stage's shapefile (and its
sidecars) to rebuild it after changing its input or processing rules.
"""

import configparser
import csv
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
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
              f"A05_Region-stats_{VERSION}.csv")
CHECKS_CSV = WORK_DIR / "region-stats-checks.csv"

AREA_CRS = 3112
CHECK_REGION_OVERLAPS = True
SLIVER_BUFFER_M = 5.0
OVERLAP_BUFFER_M = 2.5
NEAR_SAMPLE_M = 20.0
NO_MATCH = "No match"
REEF_TYPES = (("Coral Reef", "Coral"), ("Rocky Reef", "Rocky"))
PIECE_COLUMNS = ["CountFID", "RB_Type_L2", "TYPE", "NAME", "Near", "Sliver",
                 "Area_km2", "geometry"]
# field None marks CAPAD, identified by TYPE and NAME after dissolving its zones.
# Non-overlapping regionalisations are overlap checked and cut as cookie cutters.
REGIONALISATIONS = (
    {"name": "IMCRA v4.0 Meso-scale Bioregions (2023)", "slug": "imcra",
     "source": (DATA_DIR / "in-3p" / "IMCRA-v4-0-Meso-Bioregions" /
                "IMCRA-v4-Mesoscale-Bioregions.shp"),
     "field": "MESO_NAME", "overlapping": False, "simplify_m": None, "near_m": None},
    {"name": "Analysis-regions v1", "slug": "analysis-region",
     "source": (DATA_DIR / "in-3p" / "nesp-3-17-analysis-regions" /
                "analysis-regions.shp"),
     "field": "subregion", "overlapping": False, "simplify_m": None, "near_m": None},
    {"name": "CAPAD 2024 - Marine", "slug": "capad",
     "source": (DATA_DIR / "in-3p" / "CAPAD-2024" /
                "Collaborative_Australian_Protected_Areas_Database_(CAPAD)_2024_-_Marine.shp"),
     "field": None, "overlapping": True, "simplify_m": 10.0, "near_m": 300.0},
)


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
    reefs = reefs[reefs["RB_Type_L2"].isin([reef_type for reef_type, _ in REEF_TYPES])]
    reefs = reefs.to_crs(AREA_CRS)
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


def cache_suffix(setting):
    """Name suffix recording the region simplification tolerance."""
    return f"-{setting['simplify_m']:g}m" if setting["simplify_m"] else ""


def read_cached(path):
    """Read a cached layer in EPSG:3112 with TYPE and NAME identity columns."""
    layer = gpd.read_file(path).to_crs(AREA_CRS)
    if "RegionName" in layer.columns:
        layer = layer.rename(columns={"RegionName": "NAME"}).assign(TYPE="")
    layer["TYPE"] = layer["TYPE"].fillna("")
    return layer


def load_regions(setting):
    """Load named non-overlapping regions in EPSG:3112."""
    source, field, slug = setting["source"], setting["field"], setting["slug"]
    cache = WORK_DIR / f"regions-{slug}.shp"
    if cache.exists():
        print(f"Loading cached {slug} regions: {cache}", flush=True)
        return read_cached(cache)[["TYPE", "NAME", "geometry"]]

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
    return read_cached(cache)[["TYPE", "NAME", "geometry"]]


def load_capad(setting):
    """Dissolve CAPAD by TYPE and NAME, then simplify in metres."""
    source, simplify_m = setting["source"], setting["simplify_m"]
    cache = WORK_DIR / f"regions-capad{cache_suffix(setting)}.shp"
    if cache.exists():
        print(f"Loading cached CAPAD regions: {cache}", flush=True)
        return read_cached(cache)[["TYPE", "NAME", "geometry"]]

    print(f"Loading CAPAD regions: {source}", flush=True)
    regions = gpd.read_file(source)[["TYPE", "NAME", "geometry"]].to_crs(AREA_CRS)
    if (regions[["TYPE", "NAME"]].isna().any().any() or
            regions["NAME"].eq(NO_MATCH).any()):
        raise ValueError(f"Missing or reserved CAPAD identity in {source}")
    if regions.geometry.isna().any():
        raise ValueError(f"Null CAPAD geometry in {source}")
    invalid = ~regions.geometry.is_valid
    if invalid.any():
        print(f"Repairing {invalid.sum()} invalid CAPAD geometries", flush=True)
        regions.loc[invalid, "geometry"] = regions.loc[invalid, "geometry"].apply(
            lambda geometry: polygons(make_valid(geometry)))
    if regions.geometry.is_empty.any() or not regions.geometry.is_valid.all():
        raise ValueError(f"Unrepairable CAPAD geometry in {source}")
    print(f"Dissolving {len(regions)} CAPAD zones by TYPE and NAME", flush=True)
    regions = regions.dissolve(by=["TYPE", "NAME"], as_index=False)
    regions = regions[["TYPE", "NAME", "geometry"]].reset_index(drop=True)
    original = regions.geometry.copy()
    print(f"Simplifying {len(regions)} CAPAD areas to {simplify_m:g} m", flush=True)
    regions["geometry"] = regions.geometry.simplify(simplify_m, preserve_topology=True)
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
            overlaps.append({"RegionA": regions["NAME"].iloc[first],
                             "RegionB": regions["NAME"].iloc[second],
                             "geometry": intersection})
    if overlaps:
        path = WORK_DIR / f"debug-overlap-{slug}.shp"
        gpd.GeoDataFrame(overlaps, crs=regions.crs).to_file(path)
        raise ValueError(f"{len(overlaps)} region overlaps wider than 5 m; inspect {path}")


def nearest_cells(area, owners, regions, distance):
    """Split an area between regions by Voronoi cells of sampled region boundaries."""
    reach = area.buffer(distance)
    coords, labels = [], []
    for owner in owners:
        edge = regions.geometry.iloc[owner].boundary.intersection(reach)
        points = shapely.get_coordinates(shapely.segmentize(edge, NEAR_SAMPLE_M))
        coords.append(points)
        labels.append(np.full(len(points), owner))
    coords, labels = np.vstack(coords), np.concatenate(labels)
    # Voronoi merges coincident samples, such as those on shared boundaries.
    coords, first = np.unique(coords.round(1), axis=0, return_index=True)
    labels = labels[first]
    if len(set(labels.tolist())) < 2:
        return [(int(label), area) for label in set(labels.tolist())]
    points = shapely.points(coords)
    cells = list(shapely.voronoi_polygons(shapely.multipoints(coords),
                                          extend_to=reach).geoms)
    cell_index, point_index = shapely.STRtree(points).query(cells, predicate="contains")
    by_owner = {}
    for cell, point in zip(cell_index, point_index):
        by_owner.setdefault(int(labels[point]), []).append(cells[cell])
    return [(owner, unary_union(parts)) for owner, parts in by_owner.items()]


def build_near_regions(regions, reefs, setting):
    """Divide the band within near_m outside all regions by nearest region."""
    distance = setting["near_m"]
    cache = (WORK_DIR / f"near-regions-{setting['slug']}{cache_suffix(setting)}-"
             f"{distance:g}m.shp")
    if cache.exists():
        print(f"Loading near regions: {cache}", flush=True)
        return read_cached(cache)

    # Only regions within the near distance of a reef can own a near region with reef.
    _, nearby = regions.sindex.query(reefs.geometry, predicate="dwithin",
                                     distance=distance)
    candidates = sorted(set(nearby.tolist()))
    print(f"Building {distance:g} m near regions for {len(candidates)} regions",
          flush=True)
    bands = {}
    for index in candidates:
        buffer = regions.geometry.iloc[index].buffer(distance)
        blockers = regions.geometry.iloc[regions.sindex.query(buffer, predicate="intersects")]
        band = polygons(buffer.difference(unary_union(list(blockers))))
        if not band.is_empty:
            bands[index] = band
    owners = list(bands)
    band_layer = gpd.GeoSeries([bands[index] for index in owners], crs=AREA_CRS)
    first, second = band_layer.sindex.query(band_layer, predicate="intersects")
    overlaps = [polygons(band_layer.iloc[a].intersection(band_layer.iloc[b]))
                for a, b in zip(first, second) if a < b]
    contested = polygons(unary_union(overlaps)) if overlaps else Polygon()
    print(f"Resolving {contested.area / 1e6:.3f} km2 where near bands compete",
          flush=True)

    # Uncontested band is used directly; only contested areas need nearest-region tests.
    owned = {index: [polygons(bands[index].difference(contested))] for index in owners}
    components = list(contested.geoms) if isinstance(contested, MultiPolygon) else [contested]
    for component in components:
        if component.is_empty:
            continue
        competing = [owners[j] for j in
                     band_layer.sindex.query(component, predicate="intersects")]
        for owner, cell in nearest_cells(component, competing, regions, distance):
            owned[owner].append(polygons(cell.intersection(component)
                                         .intersection(bands[owner])))
    rows = []
    for index in owners:
        geometry = polygons(unary_union(owned[index]))
        if not geometry.is_empty:
            rows.append({"TYPE": regions["TYPE"].iloc[index],
                         "NAME": regions["NAME"].iloc[index], "geometry": geometry})
    near = gpd.GeoDataFrame(rows, columns=["TYPE", "NAME", "geometry"], crs=AREA_CRS)
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    near.to_file(cache)
    print(f"Cached {len(near)} near regions: {cache}", flush=True)
    return read_cached(cache)


def reef_cache_path(setting):
    """Reef piece cache named by region simplification and near distance."""
    near = f"-near{setting['near_m']:g}m" if setting["near_m"] else ""
    return WORK_DIR / f"reefs-by-{setting['slug']}{cache_suffix(setting)}{near}.shp"


def write_pieces(pieces, path, setting):
    """Save reef pieces, using RegionName for single-field regionalisations."""
    columns = [column for column in PIECE_COLUMNS[:-1] + ["Assigned", "geometry"]
               if column in pieces.columns]
    output = pieces[columns]
    if setting["field"] is not None:
        output = output.drop(columns="TYPE").rename(columns={"NAME": "RegionName"})
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    output.to_file(path)


def slice_reefs(reefs, regions, near, setting):
    """Cut each countable reef into region, near region and No match pieces."""
    cache = reef_cache_path(setting)
    if cache.exists():
        print(f"Loading reef pieces: {cache}", flush=True)
        return read_cached(cache)[PIECE_COLUMNS]

    slug, overlapping = setting["slug"], setting["overlapping"]
    print(f"Slicing {len(reefs)} countable reefs by {slug} regions", flush=True)
    rows = []
    for position, reef in enumerate(reefs.itertuples(index=False), start=1):
        by_key = {}
        remaining = reef.geometry
        for region_index in regions.sindex.query(reef.geometry, predicate="intersects"):
            region = regions.iloc[region_index]
            # Overlapping regions each take their full intersection with the reef;
            # otherwise claimed area is removed so it cannot be claimed twice.
            source = reef.geometry if overlapping else remaining
            piece = polygons(source.intersection(region.geometry))
            if piece.is_empty:
                continue
            by_key.setdefault((region.TYPE, region.NAME, 0), []).append(piece)
            if not overlapping:
                remaining = polygons(remaining.difference(region.geometry))
                if remaining.is_empty:
                    break
        if overlapping and by_key:
            inside = unary_union([part for parts in by_key.values() for part in parts])
            remaining = polygons(reef.geometry.difference(inside))
        if near is not None and not remaining.is_empty:
            for near_index in near.sindex.query(remaining, predicate="intersects"):
                zone = near.iloc[near_index]
                piece = polygons(remaining.intersection(zone.geometry))
                if piece.is_empty:
                    continue
                by_key.setdefault((zone.TYPE, zone.NAME, 1), []).append(piece)
                remaining = polygons(remaining.difference(zone.geometry))
                if remaining.is_empty:
                    break
        if not remaining.is_empty:
            by_key[("", NO_MATCH, 0)] = [remaining]

        for (region_type, name, is_near), parts in by_key.items():
            piece = polygons(unary_union(parts))
            if piece.is_empty:
                continue
            rows.append({"CountFID": reef.CountFID, "RB_Type_L2": reef.RB_Type_L2,
                         "TYPE": region_type, "NAME": name, "Near": is_near,
                         "Sliver": int(piece.buffer(-SLIVER_BUFFER_M).is_empty),
                         "Area_km2": piece.area / 1e6, "geometry": piece})
        if position % 1000 == 0:
            print(f"  {slug}: {position}/{len(reefs)} reefs", flush=True)

    pieces = gpd.GeoDataFrame(rows, columns=PIECE_COLUMNS, crs=AREA_CRS)
    write_pieces(pieces, cache, setting)
    print(f"Cached {len(pieces)} reef pieces: {cache}", flush=True)
    return pieces


def assign_counts(pieces, reef_areas):
    """Count each reef in its largest piece and in any region holding over half of it."""
    pieces = pieces.copy()
    kept = pieces["Sliver"] == 0
    # Ties favour a region, then a near region, then No match.
    priority = np.where(pieces["NAME"].eq(NO_MATCH), 2, np.where(pieces["Near"].eq(1), 1, 0))
    ranked = (pieces.assign(_priority=priority)[kept]
              .sort_values(["CountFID", "Area_km2", "_priority"],
                           ascending=[True, False, True]))
    pieces["Winner"] = 0
    pieces.loc[ranked.drop_duplicates("CountFID").index, "Winner"] = 1
    majority = kept & (pieces["Area_km2"] > 0.5 * pieces["CountFID"].map(reef_areas))
    pieces["Assigned"] = ((pieces["Winner"] == 1) | majority).astype(int)
    return pieces


def union_area(pieces):
    """Sum, over reefs, the area of the union of each reef's pieces."""
    return sum(unary_union(list(group)).area if len(group) > 1 else group.iloc[0].area
               for _, group in pieces.geometry.groupby(pieces["CountFID"]))


def check_conservation(pieces, reefs, dataset_name):
    """Check that each reef is counted once and that reef area is fully accounted for."""
    results = []
    for reef_type, _ in REEF_TYPES:
        input_reefs = reefs[reefs["RB_Type_L2"] == reef_type]
        typed = pieces[pieces["RB_Type_L2"] == reef_type]
        kept = typed[typed["Sliver"] == 0]
        is_inside = (typed["Near"] == 0) & typed["NAME"].ne(NO_MATCH)
        inside, outside = typed[is_inside], typed[~is_inside]
        kept_inside = inside[inside["Sliver"] == 0]
        kept_union = union_area(kept_inside) if len(kept_inside) else 0.0
        raw_union = union_area(inside) if len(inside) else 0.0
        outside_kept = outside.loc[outside["Sliver"] == 0].geometry.area.sum()
        outside_sliver = outside.loc[outside["Sliver"] == 1].geometry.area.sum()
        input_area = input_reefs.geometry.area.sum()
        allocated = kept_union + outside_kept
        sliver = raw_union - kept_union + outside_sliver
        winners = kept[kept["Winner"] == 1]
        tolerance = max(1.0, input_area * 1e-8)
        passed = (len(winners) == len(input_reefs) and winners["CountFID"].is_unique and
                  abs(input_area - allocated - sliver) <= tolerance)
        results.append({
            "Region_dataset": dataset_name, "RB_Type_L2": reef_type,
            "Input_reef_count": len(input_reefs),
            "Assigned_reef_count": len(winners),
            "Overlap_extra_count": int(kept["Assigned"].sum()) - len(winners),
            "Split_reef_count": int((kept.groupby("CountFID").size() > 1).sum()),
            "Partial_count_sum": int((kept["Assigned"] == 0).sum()),
            "Near_assigned_count": int((winners["Near"] == 1).sum()),
            "No_match_assigned_count": int(winners["NAME"].eq(NO_MATCH).sum()),
            "Input_area_km2": f"{input_area / 1e6:.6f}",
            "Allocated_area_km2": f"{allocated / 1e6:.6f}",
            "Sliver_area_km2": f"{sliver / 1e6:.6f}",
            "Overlap_extra_area_km2":
                f"{(kept_inside.geometry.area.sum() - kept_union) / 1e6:.6f}",
            "Status": "Pass" if passed else "Fail"})
    return results


def write_csv(path, rows):
    """Write dictionaries to CSV in their key order."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def region_label(region_type, name, near):
    """Report label of the form '{Near: }{Region_name}{ - Region_type}'."""
    label = f"Near: {name}" if near else name
    return f"{label} - {region_type}" if region_type else label


def summarise(datasets):
    """Write assigned counts, partial counts and clipped areas for each occupied region."""
    records = []
    for dataset_name, pieces in datasets:
        kept = pieces[pieces["Sliver"] == 0]
        for (region_type, name, near), group in kept.groupby(["TYPE", "NAME", "Near"]):
            record = {"Region_dataset": dataset_name, "Region_type": region_type,
                      "Region_name": name, "Near_region": "Yes" if near else "No",
                      "Label": region_label(region_type, name, near)}
            for reef_type, prefix in REEF_TYPES:
                typed = group[group["RB_Type_L2"] == reef_type]
                record[f"{prefix}_reef_count"] = int(typed["Assigned"].sum())
                record[f"{prefix}_reef_partial_count"] = int((typed["Assigned"] == 0).sum())
                record[f"{prefix}_reef_area_km2"] = f"{typed['Area_km2'].sum():.6f}"
            records.append(record)
    records.sort(key=lambda row: (row["Region_dataset"], row["Region_name"] == NO_MATCH,
                                  row["Region_type"], row["Region_name"],
                                  row["Near_region"]))
    write_csv(OUTPUT_CSV, records)
    print(f"Wrote {len(records)} region summaries: {OUTPUT_CSV}", flush=True)
    return records


def export_region_stats(regions, near, records, setting):
    """Attach CSV totals to occupied regions and near regions for mapping."""
    stats = {(row["Region_type"], row["Region_name"], int(row["Near_region"] == "Yes")): row
             for row in records
             if row["Region_dataset"] == setting["name"] and row["Region_name"] != NO_MATCH}
    layers = [regions.assign(Near=0)]
    if near is not None:
        layers.append(near.assign(Near=1))
    combined = gpd.GeoDataFrame(pd.concat(layers, ignore_index=True), crs=AREA_CRS)
    matching = [stats.get(key) for key in
                zip(combined["TYPE"], combined["NAME"], combined["Near"])]
    mapped = combined.loc[[row is not None for row in matching]].copy()
    matching = [row for row in matching if row is not None]
    mapped["Label"] = [row["Label"] for row in matching]
    for _, prefix in REEF_TYPES:
        mapped[f"{prefix}Count"] = [row[f"{prefix}_reef_count"] for row in matching]
        mapped[f"{prefix}Part"] = [row[f"{prefix}_reef_partial_count"] for row in matching]
        mapped[f"{prefix}Km2"] = [float(row[f"{prefix}_reef_area_km2"]) for row in matching]
    if setting["field"] is not None:
        mapped = mapped.drop(columns="TYPE").rename(columns={"NAME": "RegionName"})
    mapped = mapped[[column for column in mapped.columns if column != "geometry"] +
                    ["geometry"]]
    path = (OUTPUT_CSV.parent /
            f"A05_Region-stats_{setting['slug']}_{VERSION}.shp")
    mapped.to_file(path)
    print(f"Wrote {len(mapped)} occupied {setting['slug']} regions: {path}", flush=True)


def main():
    """Run each regionalisation independently against the same countable reefs."""
    reefs = load_countable()
    reef_areas = pd.Series(reefs.geometry.area.values / 1e6, index=reefs["CountFID"])
    datasets, checks, layers = [], [], []
    for setting in REGIONALISATIONS:
        print(f"Processing {setting['name']}", flush=True)
        if setting["field"] is None:
            regions = load_capad(setting)
        else:
            regions = load_regions(setting)
        if CHECK_REGION_OVERLAPS and not setting["overlapping"]:
            print(f"Checking {len(regions)} {setting['slug']} regions for overlaps",
                  flush=True)
            check_overlaps(regions, setting["slug"])
        near = build_near_regions(regions, reefs, setting) if setting["near_m"] else None
        pieces = assign_counts(slice_reefs(reefs, regions, near, setting), reef_areas)
        write_pieces(pieces, reef_cache_path(setting), setting)
        checks.extend(check_conservation(pieces, reefs, setting["name"]))
        datasets.append((setting["name"], pieces))
        layers.append((setting, regions, near))

    write_csv(CHECKS_CSV, checks)
    print(f"Wrote conservation checks: {CHECKS_CSV}", flush=True)
    records = summarise(datasets)
    for setting, regions, near in layers:
        export_region_stats(regions, near, records, setting)

    for check in checks:
        print(f"{check['Status']}: {check['Region_dataset']} {check['RB_Type_L2']}: "
              f"{check['Assigned_reef_count']}/{check['Input_reef_count']} reefs assigned, "
              f"{check['Overlap_extra_count']} overlap extras, "
              f"{check['Partial_count_sum']} partials; area "
              f"{check['Allocated_area_km2']} + slivers {check['Sliver_area_km2']} "
              f"of {check['Input_area_km2']} km2", flush=True)
    failures = [check for check in checks if check["Status"] != "Pass"]
    if failures:
        print(f"WARNING: {len(failures)} conservation checks failed; see {CHECKS_CSV}",
              flush=True)


if __name__ == "__main__":
    main()