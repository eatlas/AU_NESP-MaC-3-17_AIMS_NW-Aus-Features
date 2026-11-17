"""Explain the difference between reef boundary reef area and UQ benthic hard substrate area.

Compares Coral Reef + Rocky Reef (RB_Type_L2) in the L3 boundaries with Rock + Rubble +
Coral/Algae in the UQ benthic habitat map, for the six A07 Analysis-regions v1 subregions.
The L3 boundaries and the subregions are rasterised onto the 10 m benthic grid by pixel
centre and each pixel is weighted by its WGS84 ellipsoid area, the same method as the UQ
A02 statistics. Each table row is measured directly. The habitat totals are checked
against the published A02 CSV rather than taken from it. See
A07b-habitat-boundary-reconciliation-spec.md for the method and how to read the tables.

Run 01a-download-input-data.py first to obtain the benthic GeoTIFF and the A02 CSV.
The overlay is cached in working/{version}/A07b/ and recalculated when an input is newer.
"""

import configparser
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from osgeo import gdal, ogr
from pyproj import Geod
from shapely import box

gdal.UseExceptions()

ROOT = Path(__file__).resolve().parent
config = configparser.ConfigParser()
config.read(ROOT / "config.ini")
VERSION = config.get("general", "version")
DATA_DIR = ROOT / "data" / VERSION
L3_DATASET = (DATA_DIR / "out" / "full-classes" /
              f"AU_NESP-MaC-3-17_AIMS_NW-Aus-Features_L3_{VERSION}.shp")
REGIONS = DATA_DIR / "in-3p" / "nesp-3-17-analysis-regions" / "analysis-regions.shp"
HABITAT_DIR = DATA_DIR / "in-3p" / "UQ-shallow-habitat"
BENTHIC = HABITAT_DIR / "NW_NESP-MaC-3-17_UQ_Shallow-habitat_Benthic_2025.tif"
HABITAT_CSV = HABITAT_DIR / "A02_Habitat-area-stats.csv"
WORK_DIR = ROOT / "working" / VERSION / "A07b"
OVERLAY_CSV = WORK_DIR / "benthic-by-feature.csv"
OUTPUT_DIR = DATA_DIR / "out" / "stats"
OUTPUT_CSV = OUTPUT_DIR / f"A07b_Habitat-boundary-reconciliation_{VERSION}.csv"
OUTPUT_MD = OUTPUT_DIR / f"A07b_Habitat-boundary-reconciliation_{VERSION}.md"

SUBREGIONS = (
    "North (Nearshore)", "North (Offshore)",
    "North-west (Nearshore)", "North-west (Offshore)",
    "South-west (Nearshore)", "South-west (Offshore)",
)
REEF_L2 = ("Coral Reef", "Rocky Reef")
NOT_TARGETED_L3 = ("Coral Reef Bank", "Paleo Coast Rocky Reef")
HARD = ("Coral/Algae", "Rock", "Rubble")
SAND = ("Sand",)
OTHER_SOFT = ("Seagrass", "Light seagrass", "Microalgal mats")
NO_CLASS = "No habitat class"
NO_BOUNDARY = "No boundary feature"
TILE = 4096
# Australian Albers (equal-area). EPSG:3112 is conformal and misstates area by up to 7% here.
AREA_CRS = 3577
# Allowed relative difference between this overlay and the published A02 class areas
A02_TOLERANCE = 0.005
# Allowed relative difference between boundary polygon area and its pixel-centre rasterisation
RASTER_TOLERANCE = 0.005
# Table 3 only uses features whose rasterised area is at least this fraction classified
COVERAGE_MIN = 0.95
# Reef types with fewer included features than this are too few to describe
MIN_FEATURES = 2


def benthic_class_names(path):
    """Benthic class names by raster value, from the published A02 statistics."""
    habitat = pd.read_csv(path, encoding="utf-8-sig")
    benthic = habitat[habitat["Mapping"] == "Benthic"][["Class_id", "Class_name"]]
    names = benthic.drop_duplicates().set_index("Class_id")["Class_name"]
    if names.index.duplicated().any():
        raise ValueError("A02 CSV has more than one name for a benthic Class_id")
    expected = set(HARD + SAND + OTHER_SOFT)
    if set(names) != expected:
        raise ValueError(f"A02 benthic classes {sorted(names)} differ from {sorted(expected)}")
    return names.to_dict()


def a02_areas(path):
    """Published benthic class area (km2) per subregion, as a Region_name x Class_name table."""
    habitat = pd.read_csv(path, encoding="utf-8-sig")
    rows = habitat[(habitat["Regionalisation"] == "Analysis-regions v1") &
                   (habitat["Mapping"] == "Benthic") &
                   habitat["Region_name"].isin(SUBREGIONS)]
    if rows.duplicated(["Region_name", "Class_name"]).any():
        raise ValueError("A02 CSV has duplicate benthic rows for a subregion and class")
    return rows.pivot(index="Region_name", columns="Class_name", values="Area_km2").fillna(0.0)


def load_inputs(raster_crs):
    regions = gpd.read_file(REGIONS)
    if "subregion" not in regions.columns:
        raise ValueError("Analysis-regions shapefile has no subregion field")
    regions = regions[regions["subregion"].isin(SUBREGIONS)].to_crs(raster_crs)
    counts = regions["subregion"].value_counts()
    if set(counts.index) != set(SUBREGIONS) or (counts != 1).any():
        raise ValueError(f"Expected one polygon per subregion; found {counts.to_dict()}")
    regions = regions.set_index("subregion").loc[list(SUBREGIONS)].reset_index()

    reefs = gpd.read_file(L3_DATASET)
    missing = {"RB_Type_L2", "RB_Type_L3"} - set(reefs.columns)
    if missing:
        raise ValueError(f"L3 boundary shapefile is missing {sorted(missing)}")
    if len(reefs) >= np.iinfo(np.uint16).max:
        raise ValueError("Too many boundary features to rasterise as UInt16 ids")
    reefs = reefs[["RB_Type_L2", "RB_Type_L3", "geometry"]].reset_index(drop=True)
    # 'rid' rather than 'fid', which GeoPackage reserves
    reefs["rid"] = np.arange(1, len(reefs) + 1)
    return regions, reefs.to_crs(raster_crs)


def row_areas_km2(x0, dx, y0, dy, ny):
    """Area of one pixel in each raster row on the WGS84 ellipsoid."""
    geod = Geod(ellps="WGS84")
    lat = y0 + dy * np.arange(ny + 1)
    return np.array([abs(geod.polygon_area_perimeter(
        [x0, x0 + dx, x0 + dx, x0], [lat[i], lat[i], lat[i + 1], lat[i + 1]])[0])
        for i in range(ny)]) / 1e6


def rasterize(layer, attr, width, height, gt, projection):
    mem = gdal.GetDriverByName("MEM").Create("", width, height, 1, gdal.GDT_UInt16)
    mem.SetGeoTransform(gt)
    mem.SetProjection(projection)
    layer.SetSpatialFilterRect(gt[0], gt[3] + height * gt[5], gt[0] + width * gt[1], gt[3])
    gdal.RasterizeLayer(mem, [1], layer, options=[f"ATTRIBUTE={attr}"])
    return mem.GetRasterBand(1).ReadAsArray()


def overlay(src, regions, reefs, class_names):
    """Area (km2) of each benthic class by subregion and boundary feature (rid 0 = no feature)."""
    band = src.GetRasterBand(1)
    projection = src.GetProjection()
    x0, dx, _, y0, _, dy = src.GetGeoTransform()
    nx, ny = src.RasterXSize, src.RasterYSize
    row_area = row_areas_km2(x0, dx, y0, dy, ny)
    regions = regions.assign(rcode=np.arange(1, len(regions) + 1))

    WORK_DIR.mkdir(parents=True, exist_ok=True)
    reefs[["rid", "geometry"]].to_file(WORK_DIR / "reefs.gpkg", driver="GPKG")
    regions[["rcode", "geometry"]].to_file(WORK_DIR / "regions.gpkg", driver="GPKG")
    reef_ds = ogr.Open(str(WORK_DIR / "reefs.gpkg"))
    region_ds = ogr.Open(str(WORK_DIR / "regions.gpkg"))
    reef_layer, region_layer = reef_ds.GetLayer(0), region_ds.GetLayer(0)

    nf = len(reefs) + 1
    codes, sums = [], []
    tiles = [(tx, ty) for ty in range(0, ny, TILE) for tx in range(0, nx, TILE)]
    for i, (tx, ty) in enumerate(tiles, 1):
        if i % 500 == 0 or i == len(tiles):
            print(f"  Overlay tile {i}/{len(tiles)}", flush=True)
        w, h = min(TILE, nx - tx), min(TILE, ny - ty)
        gt = (x0 + tx * dx, dx, 0, y0 + ty * dy, 0, dy)
        tile_box = box(gt[0], gt[3] + h * dy, gt[0] + w * dx, gt[3])
        if len(regions.sindex.query(tile_box)) == 0:
            continue
        ben = band.ReadAsArray(tx, ty, w, h)
        has_reefs = len(reefs.sindex.query(tile_box)) > 0
        if not has_reefs and not ben.any():
            continue
        t = (rasterize(reef_layer, "rid", w, h, gt, projection) if has_reefs
             else np.zeros((h, w), np.uint16))
        mask = (ben > 0) | (t > 0)
        if not mask.any():
            continue
        r = rasterize(region_layer, "rcode", w, h, gt, projection)
        mask &= r > 0
        if not mask.any():
            continue
        idx = (r[mask].astype(np.int64) * nf + t[mask]) * 256 + ben[mask]
        weights = np.broadcast_to(row_area[ty:ty + h, None], (h, w))[mask]
        unique, inverse = np.unique(idx, return_inverse=True)
        codes.append(unique)
        sums.append(np.bincount(inverse, weights=weights))

    acc = pd.Series(np.concatenate(sums)).groupby(np.concatenate(codes)).sum()
    code = acc.index.to_numpy()
    ov = pd.DataFrame({"rcode": code // (nf * 256), "rid": (code // 256) % nf,
                       "bc": code % 256, "Area_km2": acc.to_numpy()})
    unknown = sorted(set(ov["bc"]) - set(class_names) - {0})
    if unknown:
        raise ValueError(f"Benthic raster has values not in the A02 class list: {unknown}")
    ov["subregion"] = ov["rcode"].map(dict(zip(regions["rcode"], regions["subregion"])))
    ov["Benthic"] = ov["bc"].map({0: NO_CLASS, **class_names})
    ov = ov.join(reefs.set_index("rid")[["RB_Type_L2", "RB_Type_L3"]], on="rid")
    ov[["RB_Type_L2", "RB_Type_L3"]] = ov[["RB_Type_L2", "RB_Type_L3"]].fillna(NO_BOUNDARY)
    return ov[["subregion", "rid", "RB_Type_L2", "RB_Type_L3", "Benthic", "Area_km2"]]


def feature_flags(regions, reefs, extent):
    """Per feature: whether it touches the six subregions and whether it lies wholly inside
    both the subregions and the habitat raster extent."""
    region_union = shapely.union_all(regions.geometry.to_numpy())
    shapely.prepare(region_union)
    shapely.prepare(extent)
    geoms = reefs.geometry.to_numpy()
    flags = reefs[["rid", "RB_Type_L2", "RB_Type_L3"]].copy()
    flags["in_regions"] = shapely.intersects(geoms, region_union)
    flags["inside"] = (shapely.covered_by(geoms, region_union) &
                       shapely.covered_by(geoms, extent))
    return flags.set_index("rid")


def vector_areas(regions, reefs, extent):
    """Coral and rocky reef L3 area (km2) per subregion, in total and inside the raster extent."""
    reefs = reefs[reefs["RB_Type_L2"].isin(REEF_L2)]
    total, inside = {}, {}
    for name, region in zip(regions["subregion"], regions.geometry):
        candidates = reefs.iloc[reefs.sindex.query(region, predicate="intersects")]
        clipped = gpd.GeoSeries(candidates.geometry.intersection(region), crs=reefs.crs)
        total[name] = clipped.to_crs(AREA_CRS).area.sum() / 1e6
        inside[name] = clipped.intersection(extent).to_crs(AREA_CRS).area.sum() / 1e6
    return pd.Series(total), pd.Series(inside)


def by_region(df):
    return df.groupby("subregion")["Area_km2"].sum().reindex(SUBREGIONS, fill_value=0.0)


def reconciliation(ov, vec_total, vec_inside):
    """Reconciliation rows as (key, label, kind, source, per-subregion Series), kind 'total',
    '-' or '+', and the no-class area that is Coral Reef Bank or Paleo Coast Rocky Reef."""
    reef = ov[ov["RB_Type_L2"].isin(REEF_L2)]
    other = ov[~ov["RB_Type_L2"].isin(REEF_L2 + (NO_BOUNDARY,))]
    outside = ov[ov["RB_Type_L2"] == NO_BOUNDARY]
    no_class = reef["Benthic"] == NO_CLASS

    boundary = vec_total.reindex(SUBREGIONS)
    footprint = by_region(reef)
    raster_diff = (vec_inside.reindex(SUBREGIONS) - footprint).abs()
    print(f"  Boundary polygons vs rasterised footprint: largest difference {raster_diff.max():.2f} km2")
    if (raster_diff > RASTER_TOLERANCE * footprint + 1).any():
        raise AssertionError(f"Rasterised boundary area differs from polygons:\n{raster_diff}")
    overlap = by_region(reef[reef["Benthic"].isin(HARD)])
    hard_other = by_region(other[other["Benthic"].isin(HARD)])
    hard_outside = by_region(outside[outside["Benthic"].isin(HARD)])
    habitat = overlap + hard_other + hard_outside
    split_boundary = "Reef boundaries split by habitat class"
    split_habitat = "Habitat hard substrate split by boundary type"
    minus = [
        ("extent", "Outside the habitat mapping extent",
         "Reef boundaries beyond the habitat raster", boundary - footprint),
        ("no_class", NO_CLASS, split_boundary, by_region(reef[no_class])),
        ("sand", "Habitat class Sand", split_boundary,
         by_region(reef[reef["Benthic"].isin(SAND)])),
        ("soft", "Habitat class Seagrass, Light seagrass or Microalgal mats", split_boundary,
         by_region(reef[reef["Benthic"].isin(OTHER_SOFT)])),
    ]
    if not np.allclose(boundary - sum(s for *_, s in minus), overlap, atol=1e-6):
        raise AssertionError("Boundary components do not sum to the overlap")
    rows = [
        ("boundary", "Reef boundary mapping: Coral Reef and Rocky Reef", "total",
         "Reef boundaries", boundary),
        *[(key, label, "-", source, s) for key, label, source, s in minus],
        ("overlap", "Overlap: reef boundaries with habitat class Rock, Rubble or Coral/Algae",
         "total", split_boundary, overlap),
        ("hard_other", "Rock, Rubble or Coral/Algae in other boundary types", "+",
         split_habitat, hard_other),
        ("hard_outside", "Rock, Rubble or Coral/Algae outside all boundary features", "+",
         split_habitat, hard_outside),
        ("habitat", "Habitat mapping: Rock, Rubble and Coral/Algae", "total",
         "Habitat raster", habitat),
    ]
    bank_paleo = by_region(reef[no_class & reef["RB_Type_L3"].isin(NOT_TARGETED_L3)])
    return rows, bank_paleo


def check_against_a02(ov, a02):
    """Stop if the overlay's benthic class areas differ from the published A02 areas."""
    mine = (ov[ov["Benthic"] != NO_CLASS]
            .pivot_table(index="subregion", columns="Benthic", values="Area_km2",
                         aggfunc="sum", fill_value=0.0)
            .reindex(index=a02.index, columns=a02.columns, fill_value=0.0))
    rel = ((mine - a02).abs() / a02.where(a02 > 1)).max().max()
    hard_rel = ((mine[list(HARD)].sum(axis=1) - a02[list(HARD)].sum(axis=1)).abs() /
                a02[list(HARD)].sum(axis=1)).max()
    print(f"  Overlay vs A02: largest class difference {rel:.2%}, "
          f"largest hard-substrate difference {hard_rel:.2%}")
    if rel > A02_TOLERANCE or hard_rel > A02_TOLERANCE:
        raise ValueError(f"Overlay differs from published A02 areas by more than {A02_TOLERANCE:.1%}")


def fmt(value, kind="area"):
    if kind == "pct":
        if pd.isna(value):
            return ""
        return "<1%" if 0 < value < 0.5 else f"{value:.0f}%"
    return "<1" if 0 < value < 0.5 else f"{round(value):,}"


def markdown_table(header, rows, align):
    lines = ["| " + " | ".join(header) + " |", "| " + " | ".join(align) + " |"]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return lines


def label_cell(label, kind):
    if kind == "total":
        return f"**{label}**"
    return {"-": "− ", "+": "+ "}.get(kind, "") + label


def report_table(rows, bank_paleo, south):
    """Six subregions combined, with each row as % of the boundary or habitat total and an
    explanation, sized for the report page."""
    totals = {key: s.sum() for key, _, _, _, s in rows}
    explain = {
        "boundary": "All coral and rocky reef boundary features in the six subregions.",
        "extent": f"Reef boundary area south of {south:.1f}°S, beyond the edge of the "
                  "habitat mapping.",
        "no_class": "Reef boundary area inside the habitat mapping extent that has no habitat "
                    "class, mostly because it is too deep or turbid to see the seabed. "
                    f"{fmt(bank_paleo.sum())} km² of this is Coral Reef Bank and Paleo Coast "
                    "Rocky Reef, which are mostly deeper than the habitat mapping can see.",
        "sand": "Sand inside reef boundaries, such as on reef flats, in lagoons and between "
                "patches of reef.",
        "soft": "Seagrass, light seagrass or microalgal mats inside reef boundaries.",
        "overlap": "Reef boundary area that the habitat mapping classes as hard substrate. "
                   "Both mappings agree that this area is reef.",
        "hard_other": "Hard substrate inside boundary features that are not coral or rocky "
                      "reef, mostly Sand Bank and High Intertidal Sediment Reef. These are "
                      "largely sediment, so this is probably patches of rubble or rock within "
                      "them.",
        "hard_outside": "Hard substrate outside all boundary features. The boundary mapping did "
                        "not map the shallow intertidal sediment along the coast, but the "
                        "habitat mapping did. Parts of this intertidal zone may be classed as "
                        "Rock, Rubble or Coral/Algae. The rest may be reef that the boundary "
                        "mapping missed or drew too small, or a misclassification in the "
                        "habitat mapping.",
        "habitat": "All Rock, Rubble and Coral/Algae in the habitat mapping in the six "
                    "subregions. This matches the published UQ statistics.",
    }
    # Rows down to the overlap split the boundary total; rows from the overlap on build the habitat total
    side = "boundary"
    md_rows = []
    for key, label, kind, _, s in rows:
        cells = [fmt(s.sum()),
                 fmt(100 * s.sum() / totals["boundary"], "pct") if side == "boundary" else "",
                 fmt(100 * s.sum() / totals["habitat"], "pct")
                 if side == "habitat" or key == "overlap" else ""]
        if key == "overlap":
            side = "habitat"
        if kind == "total":
            cells = [f"**{c}**" if c else c for c in cells]
        md_rows.append([label_cell(label, kind), *cells, explain[key]])
    header = ["Component", "Area (km²)", "% of reef boundary area",
              "% of habitat hard substrate", "Explanation"]
    return markdown_table(header, md_rows, [":---", "---:", "---:", "---:", ":---"])


def subregion_table(rows):
    """The reconciliation by subregion, with the source of each row and the ratios."""
    with_total = [(key, label, kind, source, pd.concat([s, pd.Series({"Total": s.sum()})]))
                  for key, label, kind, source, s in rows]
    s = {key: series for key, _, _, _, series in with_total}
    classified = s["overlap"] + s["sand"] + s["soft"]
    with_total += [
        ("", "Overlap as % of reef boundary area", "pct", "Overlap ÷ reef boundary total",
         100 * s["overlap"] / s["boundary"]),
        ("", "Reef boundary area with a habitat class, as % of reef boundary area", "pct",
         "(Overlap + Sand + Seagrass etc.) ÷ reef boundary total",
         100 * classified / s["boundary"]),
        ("", "Overlap as % of reef boundary area with a habitat class", "pct",
         "Overlap ÷ (Overlap + Sand + Seagrass etc.)", 100 * s["overlap"] / classified),
        ("", "Overlap as % of habitat hard substrate", "pct", "Overlap ÷ habitat total",
         100 * s["overlap"] / s["habitat"]),
    ]
    md_rows = []
    for _, label, kind, source, series in with_total:
        values = [fmt(v, kind) for v in series]
        if kind == "total":
            values = [f"**{v}**" for v in values]
        md_rows.append([label_cell(label, kind)] + values + [source])
    header = ["Component"] + list(SUBREGIONS) + ["Total", "Source"]
    csv = pd.DataFrame([[kind, label, source] + list(series.round(2))
                        for _, label, kind, source, series in with_total],
                       columns=["Kind", "Component", "Source"] + list(SUBREGIONS) + ["Total"])
    align = [":---"] + ["---:"] * (len(SUBREGIONS) + 1) + [":---"]
    return markdown_table(header, md_rows, align), csv


def reef_type_table(ov, flags):
    """Benthic class make-up of each coral and rocky reef L3 type, using only features that
    lie wholly in the subregions and raster extent and are almost fully classified."""
    reef = ov[ov["RB_Type_L2"].isin(REEF_L2)]
    per = reef.pivot_table(index="rid", columns="Benthic", values="Area_km2",
                           aggfunc="sum", fill_value=0.0)
    per = per.reindex(columns=list(HARD + SAND + OTHER_SOFT) + [NO_CLASS], fill_value=0.0)
    classified = per.drop(columns=NO_CLASS)
    coverage = classified.sum(axis=1) / per.sum(axis=1)
    keep = (coverage >= COVERAGE_MIN) & flags.loc[per.index, "inside"]
    types = flags[["RB_Type_L2", "RB_Type_L3"]]
    included = classified[keep].join(types)
    keys = ["RB_Type_L2", "RB_Type_L3"]
    totals = flags[flags["in_regions"] & flags["RB_Type_L2"].isin(REEF_L2)].groupby(keys).size()
    groups = [(l2, l3, included[(included["RB_Type_L2"] == l2) &
                                (included["RB_Type_L3"] == l3)], n)
              for (l2, l3), n in totals.sort_values(ascending=False).sort_index(
                  level=0, sort_remaining=False).items()]
    groups = [g for g in groups if len(g[2]) >= MIN_FEATURES]
    for l2 in REEF_L2:
        groups.append((f"**All {l2}**", "", included[included["RB_Type_L2"] == l2],
                       totals.loc[l2].sum()))
    rows = []
    for l2, l3, df, n in groups:
        area = df[list(HARD + SAND + OTHER_SOFT)].sum()
        pct = 100 * area / area.sum()
        rows.append([l2, l3, f"{len(df):,} of {n:,}", fmt(area.sum()),
                     fmt(pct[list(HARD)].sum(), "pct"), fmt(pct["Sand"], "pct"),
                     fmt(pct[list(OTHER_SOFT)].sum(), "pct")])
    header = ["RB_Type_L2", "RB_Type_L3", "Features included", "Area included (km²)",
              "Rock, Rubble, Coral/Algae", "Sand", "Seagrass, Light seagrass, Microalgal mats"]
    return markdown_table(header, rows, [":---", ":---"] + ["---:"] * 5)


CAPTION1 = (
    "**Table A07b-1.** Why the reef area in the reef boundary mapping differs from the hard "
    "substrate area in the UQ benthic habitat mapping, for the North, North-west and South-west "
    "subregions combined. The reef boundary mapping focused on coral reefs, rocky reefs, some "
    "less common reef types and some sand banks. It did not map the shallow intertidal "
    "sediment along the coast, which the habitat mapping does include. The table starts with "
    "the area of all Coral Reef and Rocky Reef "
    "boundaries. Rows marked − are parts of that area that the habitat mapping does not class "
    "as hard substrate (Rock, Rubble or Coral/Algae). What remains is the overlap, where both "
    "mappings agree. Rows marked + are hard substrate in the habitat mapping that lies outside "
    "the coral and rocky reef boundaries. Adding them to the overlap gives the habitat mapping "
    "total. Only the first and last rows come from one mapping alone. The rows in between are "
    "one mapping divided up by the other."
)
CAPTION2 = (
    "**Table A07b-2.** Make-up of each coral and rocky reef boundary type according to the UQ "
    "benthic habitat mapping, for the six subregions combined. Only boundary features that the "
    "habitat mapping covers almost completely are included. Each included feature lies wholly "
    "inside the six subregions and the habitat raster, and at least {coverage:.0%} of its area "
    "has a habitat class. Features that are partly unmapped, such as fringing reefs whose deeper "
    "outer edge has no habitat class, are left out. Features included shows the number of "
    "included features out of all features of that type in the six subregions. Types with fewer "
    "than {min_features} included features are not shown, but are counted in the All rows. "
    "Percentages are of the area of the included features."
)
CAPTION_S1 = (
    "**Table A07b-S1.** Table A07b-1 by Analysis-regions v1 subregion (km²), with the source "
    "of each row and the ratios between rows. 'Outside the habitat mapping extent' is reef "
    "boundary area beyond the edge of the habitat raster, south of {south:.1f}°S. Reef "
    "boundary area inside the raster that has no habitat class is in the '" + NO_CLASS + "' "
    "row. Reef boundary areas are measured from the polygons in an equal-area projection "
    "(EPSG:3577). Habitat areas are counted by pixel centre on the 10 m habitat grid, using "
    "ellipsoidal pixel areas."
)


def main():
    class_names = benthic_class_names(HABITAT_CSV)
    a02 = a02_areas(HABITAT_CSV)
    src = gdal.Open(str(BENTHIC))
    raster_crs = src.GetProjection()
    x0, dx, _, y0, _, dy = src.GetGeoTransform()
    extent = box(x0, y0 + src.RasterYSize * dy, x0 + src.RasterXSize * dx, y0)
    regions, reefs = load_inputs(raster_crs)

    inputs_mtime = max(p.stat().st_mtime for p in (L3_DATASET, REGIONS, BENTHIC, HABITAT_CSV))
    if OVERLAY_CSV.exists() and OVERLAY_CSV.stat().st_mtime > inputs_mtime:
        print(f"Loading cached overlay {OVERLAY_CSV}")
        ov = pd.read_csv(OVERLAY_CSV)
    else:
        print("Overlaying reef boundaries and subregions on the benthic habitat grid")
        ov = overlay(src, regions, reefs, class_names)
        ov.to_csv(OVERLAY_CSV, index=False)
    check_against_a02(ov, a02)

    print("Measuring coral and rocky reef boundary area from polygons")
    vec_total, vec_inside = vector_areas(regions, reefs, extent)
    rows, bank_paleo = reconciliation(ov, vec_total, vec_inside)
    s1_md, s1_csv = subregion_table(rows)
    flags = feature_flags(regions, reefs, extent)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    s1_csv.to_csv(OUTPUT_CSV, index=False)
    south = -extent.bounds[1]
    lines = [f"<!-- Generated by A07b-habitat-boundary-reconciliation.py from dataset version "
             f"{VERSION}. -->", "", CAPTION1, "", *report_table(rows, bank_paleo, south), "",
             CAPTION2.format(coverage=COVERAGE_MIN, min_features=MIN_FEATURES), "",
             *reef_type_table(ov, flags), "", CAPTION_S1.format(south=south), "", *s1_md]
    OUTPUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT_CSV} and {OUTPUT_MD}")


if __name__ == "__main__":
    main()
