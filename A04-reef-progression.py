"""
A04: Reef feature progression across dataset versions
-----------------------------------------------------
Analysis showing how the number (and area) of coral and rocky reefs has grown
through each version of the NW-Aus-Features reef mapping dataset, plotted
against cumulative mapping effort.

Purpose:
Demonstrate that at each stage of development more reefs were discovered
(driven by effort and by new data, e.g. bathymetry from v0.4 to v1.0), that
later versions focused on progressively smaller reefs, and give a sense of how
many reefs may still be to be discovered.

Normalisation pipeline (applied to every version so versions are comparable):
1. Load the version shapefile and reproject to EPSG:4326.
2. Apply any version-specific comparability filter (PREPROCESSORS). For v0.3
   this is the historical QGIS filter removing the semi-automated shallow
   sediment mask and the semi-automated rocky reef candidates, which are not
   comparable with the manually mapped versions.
3. Filter to the analysis region: keep features whose centroid falls inside
   the dissolved North-west + North analysis regions (analysis-regions.shp
   from the in-3p directory of the latest dataset version, named in
   config.ini [general] version). This removes the GBR, south-west, temperate
   and oceanic features so that all versions cover the same area.
4. Standardise the (version-specific) reef classification attribute to
   RB_Type_L2 using the lookup table in data/v1-2/in/RB_Type_L3_crosswalk.csv.
   Crosswalk keys may list several class values separated by semicolons; these
   are expanded. Class values absent from the crosswalk are mapped via
   CROSSWALK_OVERRIDES below (a warning is printed).
5. Keep only Coral Reef and Rocky Reef features.
6. For versions where land was not clipped (v0.1, v0.2), clip the land using
   apply_coastline_clipping() from 10-clip-land.py.
7. Cluster: dissolve touching features of the same RB_Type_L2 into single
   "fused" reefs using dissolve_to_l2_components() from reef_utils.py (the
   same logic as 13-make-RB_Type_L2.py).
8. Compute area (EPSG:3112) and effective width (diameter of a circle with
   the same area).

Countable reef pipeline (applied after step 8, before size classification):
9. cluster_countable(): buffer each fused reef by 50 m and unary-union the
    buffers to group reefs closer than the buffer into single clusters (the
    buffer is used for grouping only; core algorithm in
    reef_utils.cluster_countable, wrapped here with per-version caching).
    Each cluster is mapped back to its original (unbuffered) member reefs,
    whose union (multi-part where the members are separated) provides the
    area and effective width; clusters with effective width < 100 m are
    dropped and the survivors are re-binned into size classes. Because the
    clustering is per L2 class, every cluster is a single type. This yields
    the "countable reefs" set used for the count plots.

Integrity check:
The v1.2 L2 reef set produced by this pipeline (before the region filter,
i.e. national extent) is compared against the L2 shapefile produced by
13-make-RB_Type_L2.py. Any differences in counts, area, or geometry are
reported (they would signal a mistake in this pipeline).

Outputs (working/A04/):
- reef-progression-table.csv: per version, per reef type, per size class:
  count and area of the standard set (effective width >= 30 m), plus effort
  hours and a short version note.
- reef-progression-countable-table.csv: same layout for the countable set
  (clustered, effective width >= 100 m; size classes start at 100 m).
- figs/fig-fraction-areas.png:   standard area as % of the v1.2 values, by
  size class (left: coral reefs, right: rocky reefs), x = cumulative effort
  hours.
- figs/fig-countable-counts.png: countable count as % of the v1.2 values,
  by size class.
- figs/fig-countable-areas.png:  countable area as % of the v1.2 values,
  by size class.
- figs/fig-absolute.png: left:
  total countable reef count; right: total countable area. Coral and rocky
  reefs in both panels (all size classes, effective width >= 100 m).

Adding a new version:
Add one entry to VERSIONS below (shapefile path, class attribute, crosswalk
key column, clip_land flag, cumulative effort hours, note) and the script
picks it up. Keep VERSIONS in chronological order. Update the [general]
version in config.ini to the new version; the analysis region file is read
from its in-3p directory and applied to all versions.
"""

import configparser
import importlib.util
import os
import shutil
import sys
import time

import geopandas as gpd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from shapely.geometry import MultiPolygon, Polygon
from shapely.ops import unary_union
from shapely.validation import make_valid

# Repository root must be the working directory (config.ini, data/, reef_utils.py)
ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from reef_utils import cluster_countable as utils_cluster_countable  # noqa: E402
from reef_utils import dissolve_to_l2_components  # noqa: E402

cfg = configparser.ConfigParser()
cfg.read("config.ini")
in_3p_path = cfg.get("general", "in_3p_path")

# ---- PATH CONSTANTS ----
CROSSWALK_CSV = os.path.join("data", "v1-2", "in", "RB_Type_L3_crosswalk.csv")
COASTLINE_FILE = os.path.join(
    in_3p_path,
    "AU_AIMS_Coastline_50k_2024",
    "Split",
    "AU_NESP-MaC-3-17_AIMS_Aus-Coastline-50k_2024_V1-1_split.shp",
)
# L2 output of 13-make-RB_Type_L2.py, used for the v1.2 integrity check
V1_2_L2_SHP = os.path.join(
    "data", "v1-2", "out", "simp-classes",
    "AU_NESP-MaC-3-17_AIMS_NW-Aus-Features_L2_v1-2.shp",
)
# Analysis regions (NESP 3.17). Read from the in-3p directory of the latest
# dataset version (the [general] version in config.ini) and applied to every
# version so all versions cover the same area.
LATEST_VERSION = cfg.get("general", "version")
REGION_SHP = os.path.join(
    "data", LATEST_VERSION, "in-3p",
    "nesp-3-17-analysis-regions", "analysis-regions.shp",
)
# Regions kept in the analysis (feature centroids inside the dissolved union)
REGION_NAMES = ("North-west", "North")
OUTPUT_DIR = os.path.join("working", "A04")
FIG_DIR = os.path.join(OUTPUT_DIR, "figs")
TABLE_CSV = os.path.join(OUTPUT_DIR, "reef-progression-table.csv")
COUNTABLE_TABLE_CSV = os.path.join(OUTPUT_DIR, "reef-progression-countable-table.csv")
# Per-version cache of fused L2 reefs (delete a file to force reprocessing)
CACHE_DIR = os.path.join(OUTPUT_DIR, "cache")

# ---- ANALYSIS CONSTANTS ----
PROCESS_CRS = 4326   # geometry processing CRS (clipping needs geographic coords)
AREA_CRS = 3112      # MGRUP, for area calculations
MIN_EFF_WIDTH_M = 30.0
KEEP_L2 = ["Coral Reef", "Rocky Reef"]

# Size classes: name, min effective width (m, inclusive), max (m, exclusive)
SIZE_CLASSES = [
    ("Very Small", 30.0, 100.0),
    ("Small", 100.0, 300.0),
    ("Medium", 300.0, 1000.0),
    ("Large", 1000.0, 3000.0),
    ("Very Large", 3000.0, np.inf),
]

# ---- COUNTABLE REEF CONSTANTS ----
# Reefs closer than this are merged into a single cluster (buffer applied to
# each fused reef before the unary union).
CLUSTER_BUFFER_M = 50.0
# Clusters with an effective width below this are not "countable".
COUNTABLE_WIDTH_M = 100.0
# Size classes for the countable set (re-binned from COUNTABLE_WIDTH_M up;
# the 30-100 m class cannot occur because those reefs are dropped).
COUNTABLE_SIZE_CLASSES = [
    ("Small", 100.0, 300.0),
    ("Medium", 300.0, 1000.0),
    ("Large", 1000.0, 3000.0),
    ("Very Large", 3000.0, np.inf),
]

# Cumulative mapping effort (hours) and short purpose note for each version.
# v0.1 uses the RB map (450 hrs); the EL rough mask ran in parallel and its
# contribution is captured in the v0.2 merge.
VERSIONS = [
    dict(
        version="v0.1",
        shapefile=os.path.join("data", "v0-1_dual-maps", "Reef-Features_Ref1_RB",
                               "Reef Boundaries RB.shp"),
        class_attr="Type",
        crosswalk_key="Type_v0-1",
        clip_land=True,
        effort_hours=450.0,
        note="Initial mapping",
    ),
    dict(
        version="v0.2",
        shapefile=os.path.join("data", "v0-2_merge-maps", "Reef-boundaries-v0-2",
                               "Reef Boundaries Review RB.shp"),
        class_attr="Type",
        crosswalk_key="Type_v0-2",
        clip_land=True,
        effort_hours=550.0,
        note="Merged maps",
    ),
    dict(
        version="v0.3",
        shapefile=os.path.join("data", "v0-3_qc-1", "out",
                               "NW-Aus-Features_v0-3.shp"),
        class_attr="RB_Type_L3",
        crosswalk_key="RB_Type_L3_v0-3",
        clip_land=False,
        effort_hours=630.0,
        note="QC pass",
    ),
    dict(
        version="v0.4",
        shapefile=os.path.join("data", "v0-4", "out",
                               "AU_NESP-MaC-3-17_AIMS_NW-Aus-Features_v0-4.shp"),
        class_attr="RB_Type_L3",
        crosswalk_key="RB_Type_L3_v0-4",
        clip_land=False,
        effort_hours=707.0,
        note="Reclassification",
    ),
    dict(
        version="v1.0",
        shapefile=os.path.join("data", "v1-0", "out", "full-classes",
                               "AU_NESP-MaC-3-17_AIMS_NW-Aus-Features_L3_v1-0.shp"),
        class_attr="RB_Type_L3",
        crosswalk_key="RB_Type_L3_v0-4",
        clip_land=False,
        effort_hours=760.5,
        note="Bathymetry",
    ),
    dict(
        version="v1.1",
        shapefile=os.path.join("data", "v1-1", "out", "full-classes",
                               "AU_NESP-MaC-3-17_AIMS_NW-Aus-Features_L3_v1-1.shp"),
        class_attr="RB_Type_L3",
        crosswalk_key="RB_Type_L3_v0-4",
        clip_land=False,
        effort_hours=782.0,
        note="ReefIDs",
    ),
    dict(
        version="v1.2",
        shapefile=os.path.join("data", "v1-2", "out", "full-classes",
                               "AU_NESP-MaC-3-17_AIMS_NW-Aus-Features_L3_v1-2.shp"),
        class_attr="RB_Type_L3",
        crosswalk_key="RB_Type_L3_v0-4",
        clip_land=False,
        effort_hours=783.0,
        note="Refinement",
    ),
]

# Fallback mappings for class values not present in the crosswalk CSV.
# Only applied when the value is missing from the CSV (a warning is printed).
# Remove entries here once they are added to the crosswalk file.
# Do NOT add overrides for v0.3 "Atoll Platform" (the crosswalk maps it to
# Coral Reef) or v0.4+ "High Intertidal Sediment Reef" (its mapping to
# Sediment Reef is an intentional reclassification).
CROSSWALK_OVERRIDES = {
    "Type_v0-1": {},
    "Type_v0-2": {
        "Seagrass": "Sediment",
        "Ancient Coastline Reef": "Rocky Reef",
        "Ancient Coastline Feature": "Rocky Reef",
    },
    "RB_Type_L3_v0-3": {},
    "RB_Type_L3_v0-4": {},
}


# ---- VERSION-SPECIFIC PREPROCESSING ----
# Explicit comparability filters applied after load/CRS standardisation and
# before L2 standardisation. Add a new version's rule here and register it in
# PREPROCESSORS; process_version() applies any registered rule automatically.

def preprocess_v0_3_comparability(gdf):
    """Apply the v0.3 comparability filter (reproduces the historical QGIS filter).

    QGIS expression:
        "RB_Type_L3" != 'Shallow Sediment' AND
        "RB_Type_L3" != 'Shallow sediment' AND
        "EdgeSrc" != 'Semi-auto rocky reef'

    Rationale:
    - 'Shallow Sediment' / 'Shallow sediment' (19,567 features, EdgeSrc
      'Semi-auto shallow mask'): v0.3-specific semi-automated shallow sediment
      mask, not comparable with the sandbanks of the other versions. (They map
      to L2 'Sediment' and would be excluded by the KEEP_L2 filter anyway;
      removed here early to faithfully reproduce the QGIS filtering.)
    - EdgeSrc 'Semi-auto rocky reef' (5,496 features, all 'Fringing Rocky
      Reef'): semi-automated rocky reef candidates producing many small
      candidate/false-positive features. They map to L2 'Rocky Reef' and would
      otherwise inflate the v0.3 rocky reef counts, so they must be excluded.

    Note: the QGIS expression would also drop features with a null EdgeSrc
    (null propagation); v0.3 has no null EdgeSrc values, so the pandas
    expression below is exactly equivalent.
    """
    is_shallow_sediment = gdf["RB_Type_L3"].isin(
        ["Shallow Sediment", "Shallow sediment"]
    )
    is_semi_auto_rocky = gdf["EdgeSrc"].eq("Semi-auto rocky reef")
    drop = is_shallow_sediment | is_semi_auto_rocky
    n_drop = int(drop.sum())
    print(f"  v0.3 comparability filter: removed {n_drop} of {len(gdf)} features "
          f"({int(is_shallow_sediment.sum())} shallow sediment, "
          f"{int(is_semi_auto_rocky.sum())} semi-auto rocky reef, "
          f"{int((is_shallow_sediment & is_semi_auto_rocky).sum())} in both)")
    return gdf[~drop]


PREPROCESSORS = {
    "v0.3": preprocess_v0_3_comparability,
}


# ---- ANALYSIS REGION ----

_region_union_cache = None


def load_region_union():
    """Load the analysis regions and return the dissolved keep-region union.

    The regions shapefile is read from the in-3p directory of the latest
    dataset version (config.ini [general] version, see REGION_SHP) and is
    applied to every version so all versions cover the same area. Features
    with region in REGION_NAMES are dissolved into a single union geometry
    (EPSG:4326) used for the centroid test in filter_by_region().
    """
    global _region_union_cache
    if _region_union_cache is not None:
        return _region_union_cache
    if not os.path.exists(REGION_SHP):
        raise FileNotFoundError(
            f"Analysis regions shapefile not found: {REGION_SHP} (expected in "
            f"the in-3p directory of {LATEST_VERSION}, the [general] version "
            "in config.ini)."
        )
    regions = gpd.read_file(REGION_SHP)
    if "region" not in regions.columns:
        raise ValueError(f"{REGION_SHP} has no 'region' column")
    sel = regions[regions["region"].isin(REGION_NAMES)].to_crs(PROCESS_CRS)
    if sel.empty:
        raise ValueError(f"No features with region in {REGION_NAMES} in {REGION_SHP}")
    _region_union_cache = unary_union(sel.geometry)
    print(f"Analysis regions: keeping {', '.join(REGION_NAMES)} "
          f"({len(sel)} features) from {REGION_SHP}")
    return _region_union_cache


def filter_by_region(gdf, union, version):
    """Keep only features whose centroid falls inside the analysis region."""
    mask = gdf.geometry.centroid.within(union)
    n_drop = int((~mask).sum())
    print(f"  {version} dropped {n_drop} by region filter; {int(mask.sum())} remain")
    return gdf[mask]


def load_clip_land_module():
    """Load 10-clip-land.py as a module (its name is not a valid identifier)."""
    path = os.path.join(ROOT, "10-clip-land.py")
    spec = importlib.util.spec_from_file_location("a04_clip_land", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_crosswalk():
    """Read the crosswalk CSV and build key -> RB_Type_L2 lookups.

    Crosswalk keys may list several class values separated by semicolons
    (e.g. 'Platform Rocky Reef;Rocky Ridge'); these are expanded so each
    individual value maps to the row's RB_Type_L2.
    """
    cw = pd.read_csv(CROSSWALK_CSV)
    lookups = {}
    for key in ("Type_v0-1", "Type_v0-2", "RB_Type_L3_v0-3", "RB_Type_L3_v0-4"):
        if key not in cw.columns:
            continue
        keys, l2s = [], []
        for k, l2 in zip(cw[key], cw["RB_Type_L2"]):
            if pd.isna(k) or pd.isna(l2):
                continue
            for part in str(k).split(";"):
                part = part.strip()
                if part:
                    keys.append(part)
                    l2s.append(str(l2).strip())
        ser = pd.Series(l2s, index=keys)
        ambiguous = ser.groupby(ser.index).nunique()
        ambiguous = ambiguous[ambiguous > 1]
        if not ambiguous.empty:
            raise ValueError(
                f"Crosswalk column {key} maps keys to multiple RB_Type_L2 values: "
                f"{ambiguous.to_dict()}"
            )
        lookups[key] = ser[~ser.index.duplicated()]
    return lookups


def standardise_l2(gdf, class_attr, crosswalk_key, lookups, version):
    """Map the version's classification attribute to RB_Type_L2 via the crosswalk."""
    if class_attr not in gdf.columns:
        raise ValueError(f"{version}: shapefile missing classification column '{class_attr}'")
    if crosswalk_key not in lookups:
        raise ValueError(f"{version}: crosswalk has no column '{crosswalk_key}'")

    values = gdf[class_attr].astype(str).str.strip()
    lookup = lookups[crosswalk_key]
    overrides = CROSSWALK_OVERRIDES.get(crosswalk_key, {})

    l2 = values.map(lookup)
    if l2.isna().any():
        missing_values = values[l2.isna()]
        missing = sorted(set(missing_values.unique()))
        still_missing = [u for u in missing if u not in overrides]
        if still_missing:
            detail = {u: int((missing_values == u).sum()) for u in still_missing}
            raise ValueError(
                f"{version}: classification values not in crosswalk or overrides: "
                f"{detail}"
            )
        print(f"  WARNING: {int(l2.isna().sum())} features with class value(s) "
              f"{missing} missing from crosswalk, using overrides: "
              f"{ {u: overrides[u] for u in missing} }")
        l2 = l2.fillna(missing_values.map(overrides))
    gdf = gdf.copy()
    gdf["RB_Type_L2"] = l2.to_numpy()
    return gdf


def keep_polygons(gdf, label):
    """Drop any non-polygon geometries (should not occur, but be safe)."""
    mask = gdf.geometry.apply(lambda g: isinstance(g, (Polygon, MultiPolygon)))
    if not mask.all():
        print(f"  WARNING: dropped {int((~mask).sum())} non-polygon geometries ({label})")
        gdf = gdf[mask]
    return gdf


def clean_geometries(gdf):
    """Fix invalid geometries (buffer(0)) and drop empties."""
    gdf = gdf.copy()
    gdf["geometry"] = gdf.geometry.apply(
        lambda g: g if g.is_valid else make_valid(g)
    )
    gdf["geometry"] = gdf.geometry.buffer(0)
    return gdf[~gdf.geometry.isna() & ~gdf.geometry.is_empty]


def process_version(vspec, lookups, clip_land_module, region_union=None,
                    apply_region=True):
    """Run the full normalisation pipeline for one version.

    Returns a GeoDataFrame of fused L2 reefs (Coral Reef / Rocky Reef only)
    with Area_km2 and EffWidth_m columns. The <30 m filter and size-class
    assignment are applied separately by size_classify() so that the
    integrity check can be run on the unfiltered set.

    With apply_region=True (default) the region filter is applied and the
    result is cached. With apply_region=False the pipeline is run without
    the region filter and without touching the cache; this is used to
    recompute the national-extent v1.2 set for the integrity check against
    13-make-RB_Type_L2.py.
    """
    version = vspec["version"]
    note = vspec["note"] + ("" if apply_region else
                            " (no region filter, for integrity check)")
    print(f"\n=== {version} ({note}) ===")

    cache_file = os.path.join(CACHE_DIR, f"{version}_L2_reefs.shp")
    no_region_cache_file = os.path.join(CACHE_DIR, f"{version}_L2_reefs_no_region.shp")
    if apply_region and os.path.exists(cache_file):
        gdf = gpd.read_file(cache_file)
        print(f"  Loaded {len(gdf)} fused reefs from cache ({cache_file})")
        return gdf

    if not apply_region and os.path.exists(no_region_cache_file):
        gdf = gpd.read_file(no_region_cache_file)
        print(f"  Loaded {len(gdf)} fused reefs from cache ({no_region_cache_file})")
        return gdf

    if apply_region and version == "v1.2" and os.path.exists(no_region_cache_file):
        os.remove(no_region_cache_file)
        print(f"  Invalidated no-region cache for v1.2 (v1.2 was recalculated)")

    start_time = time.time()
    print(f"  Reading {vspec['shapefile']}")
    gdf = gpd.read_file(vspec["shapefile"])
    if gdf.crs is None or gdf.crs.to_epsg() != PROCESS_CRS:
        print(f"  Reprojecting {gdf.crs} -> EPSG:{PROCESS_CRS}")
        gdf = gdf.to_crs(PROCESS_CRS)
    print(f"  Loaded {len(gdf)} features")

    preprocessor = PREPROCESSORS.get(version)
    if preprocessor is not None:
        gdf = preprocessor(gdf)

    if apply_region and region_union is not None:
        gdf = filter_by_region(gdf, region_union, version)

    gdf = standardise_l2(gdf, vspec["class_attr"], vspec["crosswalk_key"],
                          lookups, version)
    n_before = len(gdf)
    gdf = gdf[gdf["RB_Type_L2"].isin(KEEP_L2)]
    print(f"  Kept {len(gdf)} of {n_before} features "
          f"({', '.join(KEEP_L2)} only)")

    if vspec["clip_land"] and not gdf.empty:
        gdf = clean_geometries(gdf)
        gdf = keep_polygons(gdf, f"{version} pre-clip")
        gdf = clip_land_module.apply_coastline_clipping(gdf, COASTLINE_FILE)
        gdf = keep_polygons(gdf, f"{version} post-clip")
        print(f"  {len(gdf)} features after land clipping")

    print("  Dissolving to fused L2 reefs...")
    components = dissolve_to_l2_components(gdf[["RB_Type_L2", "geometry"]])
    gdf = gpd.GeoDataFrame(
        [{"RB_Type_L2": c["l2_class"], "geometry": c["geometry"]} for c in components],
        crs=PROCESS_CRS,
    )
    print(f"  {len(gdf)} fused reefs")

    # Area and effective width (diameter of an equal-area circle)
    projected = gdf.to_crs(AREA_CRS)
    area_m2 = projected.geometry.area.to_numpy()
    gdf["Area_km2"] = area_m2 / 1e6
    gdf["EffWidth_m"] = 2.0 * np.sqrt(area_m2 / np.pi)
    gdf = gdf.dropna(subset=["EffWidth_m"])

    os.makedirs(CACHE_DIR, exist_ok=True)
    if apply_region:
        gdf.to_file(cache_file)
        countable_cache = os.path.join(CACHE_DIR, f"{version}_countable.shp")
        if os.path.exists(countable_cache):
            os.remove(countable_cache)
            print(f"  Invalidated countable reef cache for {version}")
        size_classified_cache = os.path.join(CACHE_DIR, f"{version}_size_classified.shp")
        if os.path.exists(size_classified_cache):
            os.remove(size_classified_cache)
            print(f"  Invalidated size-classified cache for {version}")
        print(f"  Cached fused reefs to {cache_file} "
              f"(total: {time.time() - start_time:.0f} s)")
    else:
        gdf.to_file(no_region_cache_file)
        print(f"  Cached fused reefs (no region filter) to {no_region_cache_file} "
              f"(total: {time.time() - start_time:.0f} s)")
    return gdf


def size_classify(gdf, version=None):
    """Drop reefs with effective width < MIN_EFF_WIDTH_M and assign size classes."""
    cache_file = None
    if version:
        cache_file = os.path.join(CACHE_DIR, f"{version}_size_classified.shp")
        if os.path.exists(cache_file):
            print(f"  Loaded size-classified reefs from cache ({cache_file})")
            return gpd.read_file(cache_file)

    n_before = len(gdf)
    gdf = gdf[gdf["EffWidth_m"] >= MIN_EFF_WIDTH_M].copy()
    print(f"  Dropped {n_before - len(gdf)} reefs with effective width < "
          f"{MIN_EFF_WIDTH_M:.0f} m")
    bins = [lo for _, lo, _ in SIZE_CLASSES] + [np.inf]
    labels = [name for name, _, _ in SIZE_CLASSES]
    gdf["SizeClass"] = pd.cut(
        gdf["EffWidth_m"], bins=bins, labels=labels, include_lowest=True
    )

    if cache_file:
        os.makedirs(CACHE_DIR, exist_ok=True)
        gdf.to_file(cache_file)
        print(f"  Cached size-classified reefs to {cache_file}")
    return gdf


def cluster_countable(gdf, version):
    """Cluster fused reefs into "countable reefs" (see
    reef_utils.cluster_countable for the algorithm).

    A04 wrapper around the shared reef_utils.cluster_countable: applies
    the A04 countable constants, per-version shapefile caching, and the
    summary print. The clustering itself (buffer grouping, measurement,
    small-cluster dropping, size binning) lives in reef_utils so it can
    be reused by other analyses with their own caching and constants.

    Input: fused L2 reefs in PROCESS_CRS with Area_km2 and EffWidth_m
    (the output of process_version, before size_classify).
    Output: GeoDataFrame in PROCESS_CRS with RB_Type_L2, Area_km2,
    EffWidth_m and SizeClass.
    """
    cache_file = os.path.join(CACHE_DIR, f"{version}_countable.shp")
    if os.path.exists(cache_file):
        out = gpd.read_file(cache_file)
        print(f"  Loaded {len(out)} countable reefs from cache ({cache_file})")
        return out

    out, stats = utils_cluster_countable(
        gdf,
        buffer_m=CLUSTER_BUFFER_M,
        min_width_m=COUNTABLE_WIDTH_M,
        drop_small=True,
        size_classes=COUNTABLE_SIZE_CLASSES,
        buffer_crs=AREA_CRS,
    )

    os.makedirs(CACHE_DIR, exist_ok=True)
    out.to_file(cache_file)
    print(f"  Cached countable reefs to {cache_file}")

    n_coral = int((out["RB_Type_L2"] == "Coral Reef").sum())
    n_rocky = int((out["RB_Type_L2"] == "Rocky Reef").sum())
    print(f"  {version} countable: {stats['n_clusters']} clusters "
          f"({stats['n_fused']} fused reefs, "
          f"{stats['n_fused'] - stats['n_clusters']} merged with neighbours), "
          f"{stats['n_dropped']} dropped by effective width < "
          f"{COUNTABLE_WIDTH_M:.0f} m, {stats['n_countable']} countable reefs "
          f"({n_coral} coral, {n_rocky} rocky)")
    return out


def check_v1_2(ours):
    """Compare our v1.2 L2 reefs against the output of 13-make-RB_Type_L2.py.

    'ours' must be the national-extent set (produced with
    apply_region=False); the 13-make-RB_Type_L2.py output is also national
    extent, so the comparison is unaffected by the analysis region filter.
    """
    print("\n=== Integrity check: v1.2 (national extent) vs "
          "13-make-RB_Type_L2.py output ===")
    ref = gpd.read_file(V1_2_L2_SHP)
    if ref.crs is None or ref.crs.to_epsg() != PROCESS_CRS:
        ref = ref.to_crs(PROCESS_CRS)
    ref = ref[ref["RB_Type_L2"].isin(KEEP_L2)].copy()
    ref["Area_km2"] = ref["Area_km2"].astype(float)

    problems = []

    for l2 in KEEP_L2:
        n_ours, n_ref = int((ours["RB_Type_L2"] == l2).sum()), int((ref["RB_Type_L2"] == l2).sum())
        a_ours = float(ours.loc[ours["RB_Type_L2"] == l2, "Area_km2"].sum())
        a_ref = float(ref.loc[ref["RB_Type_L2"] == l2, "Area_km2"].sum())
        print(f"  {l2}: ours {n_ours} reefs / {a_ours:.1f} km2   |   "
              f"script13 {n_ref} reefs / {a_ref:.1f} km2")
        if n_ours != n_ref:
            problems.append(f"{l2}: feature count differs ({n_ours} vs {n_ref})")
        if abs(a_ours - a_ref) > 1e-3 * max(a_ours, a_ref, 1.0):
            problems.append(f"{l2}: total area differs ({a_ours:.3f} vs {a_ref:.3f} km2)")

    # Geometry-level comparison via spatial join
    # 'within' matches identical/nested polygons (unlike 'overlaps', which
    # is False for equal polygons), but not merely boundary-touching
    # neighbours of a different class.
    ours_j = ours[["RB_Type_L2", "Area_km2", "geometry"]].rename(
        columns={"RB_Type_L2": "RB_Type_L2_x", "Area_km2": "Area_km2_x"}
    )
    ref_j = ref[["RB_Type_L2", "Area_km2", "geometry"]].rename(
        columns={"RB_Type_L2": "RB_Type_L2_y", "Area_km2": "Area_km2_y"}
    )
    joined = gpd.sjoin(ours_j, ref_j, predicate="within", how="left")
    unmatched_ours = ours.loc[joined.index[joined["Area_km2_y"].isna()].unique()]
    if not unmatched_ours.empty:
        problems.append(f"{len(unmatched_ours)} of our reefs have no matching "
                        f"geometry in the script-13 output")
    ref_ids = set(joined["index_right"].unique())
    unmatched_ref = ref[~ref.index.isin(ref_ids)]
    if not unmatched_ref.empty:
        problems.append(f"{len(unmatched_ref)} script-13 reefs have no matching "
                        f"geometry in our output")

    matched = joined[joined["RB_Type_L2_x"] == joined["RB_Type_L2_y"]]
    area_diff = (matched["Area_km2_x"] - matched["Area_km2_y"]).abs()
    if not matched.empty:
        print(f"  Geometry match: {len(matched)} paired reefs, max area diff "
              f"{area_diff.max():.2e} km2, mean {area_diff.mean():.2e} km2")
        if area_diff.max() > 1e-3:
            problems.append(f"max paired area difference {area_diff.max():.4f} km2")
    class_switch = joined[
        joined["RB_Type_L2_y"].notna()
        & (joined["RB_Type_L2_x"] != joined["RB_Type_L2_y"])
    ]
    if not class_switch.empty:
        problems.append(f"{len(class_switch)} reefs have a different L2 class")

    if problems:
        print("  MISMATCHES FOUND:")
        for p in problems:
            print(f"    - {p}")
    else:
        print("  OK: our v1.2 L2 reefs match the script-13 output "
              "(counts, areas, geometries).")
    return not problems


def type_key(l2):
    return l2.replace(" ", "")  # 'Coral Reef' -> 'CoralReef'


def build_table(results, size_classes):
    """Build the summary table: version x reef type x size class counts and areas."""
    rows = []
    for vspec in VERSIONS:
        gdf = results[vspec["version"]]
        row = {
            "Version": vspec["version"],
            "Effort_hours": vspec["effort_hours"],
            "Version_Note": vspec["note"],
        }
        for l2 in KEEP_L2:
            sub = gdf[gdf["RB_Type_L2"] == l2]
            for name, _, _ in size_classes:
                cls = sub[sub["SizeClass"] == name]
                col_base = f"{type_key(l2)}_{name.replace(' ', '')}"
                row[f"N_{col_base}"] = len(cls)
                row[f"Area_km2_{col_base}"] = float(cls["Area_km2"].sum())
            row[f"N_{type_key(l2)}_Total"] = len(sub)
            row[f"Area_km2_{type_key(l2)}_Total"] = float(sub["Area_km2"].sum())
        rows.append(row)

    table = pd.DataFrame(rows)
    cols = ["Version", "Effort_hours", "Version_Note"]
    for l2 in KEEP_L2:
        cols += [f"N_{type_key(l2)}_{n.replace(' ', '')}" for n, _, _ in size_classes]
        cols += [f"N_{type_key(l2)}_Total"]
        cols += [f"Area_km2_{type_key(l2)}_{n.replace(' ', '')}" for n, _, _ in size_classes]
        cols += [f"Area_km2_{type_key(l2)}_Total"]
    return table[cols]


# ---- PLOTTING ----

CLASS_COLORS = {
    "Very Small": "#6baed6",
    "Small": "#3183bd",
    "Medium": "#e6550d",
    "Large": "#a6360c",
    "Very Large": "#31a354",
}
TYPE_COLORS = {"Coral Reef": "#e6550d", "Rocky Reef": "#3183bd"}


def _set_version_ticks(ax, vspecs, x_metric="effort_hours"):
    """Continuous x-axis in x_metric units with the version labels at each
    version's position (so equal effort increments get equal axis space)."""
    ax.set_xticks([v[x_metric] for v in vspecs])
    ax.set_xticklabels([f"{v[x_metric]:.0f}\n{v['version']}" for v in vspecs],
                       rotation=0, ha="right")
    ax.set_xlabel("Cumulative mapping effort (hours)")


def plot_fraction(table, metric, filename, suptitle,
                  size_classes=SIZE_CLASSES, x_metric="effort_hours"):
    """One line per size class, values as % of the final (v1.2) values.

    metric: 'N' or 'Area_km2'
    """
    vspecs = VERSIONS
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.5), sharey=True)
    for ax, l2 in zip(axes, KEEP_L2):
        for name, _, _ in size_classes:
            col = f"{metric}_{type_key(l2)}_{name.replace(' ', '')}"
            vals = table[col].to_numpy(dtype=float)
            final = vals[-1]
            frac = np.where(final > 0, vals / final * 100.0, np.nan)
            ax.plot([v[x_metric] for v in vspecs], frac,
                    marker="o", lw=1.5, color=CLASS_COLORS[name], label=name)
        _set_version_ticks(ax, vspecs, x_metric)
        ax.set_title(l2)
        ax.set_ylim(20, 150)
        ax.grid(alpha=0.3)
        ax.legend(loc="lower right", fontsize=9)
    axes[0].set_ylabel(f"% of v1.2 {'count' if metric == 'N' else 'area'}")
    fig.suptitle(suptitle)
    fig.tight_layout()
    out = os.path.abspath(os.path.join(FIG_DIR, filename))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    try:
        fig.savefig(out, dpi=150)
    except OSError as e:
        raise OSError(
            f"Failed to save figure to {out}: {e}\n"
            f"  Check that the directory exists and you have write permissions."
        )
    plt.close(fig)
    print(f"  Saved {out}")


def plot_absolute(table, filename, size_classes, min_width_m,
                  x_metric="effort_hours"):
    """Total count and total area over the given size classes."""
    vspecs = VERSIONS
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.5))
    x_vals = [v[x_metric] for v in vspecs]
    for l2 in KEEP_L2:
        n_total = sum(
            table[f"N_{type_key(l2)}_{n.replace(' ', '')}"] for n, _, _ in size_classes
        )
        axes[0].plot(x_vals, n_total.to_numpy(float),
                     marker="o", lw=1.5, color=TYPE_COLORS[l2], label=l2)
    a_rocky_series = table[f"Area_km2_RockyReef_Total"].to_numpy(float)
    a_coral_series = table[f"Area_km2_CoralReef_Total"].to_numpy(float)
    a_total_series = a_rocky_series + a_coral_series
    axes[1].fill_between(x_vals, 0, a_rocky_series,
                         color=TYPE_COLORS["Rocky Reef"], alpha=0.8,
                         label="Rocky reef area")
    axes[1].fill_between(x_vals, a_rocky_series, a_total_series,
                         color=TYPE_COLORS["Coral Reef"], alpha=0.8,
                         label="Coral reef area")
    axes[1].plot(x_vals, a_total_series, "k-", marker="o", lw=1, alpha=0.5)
    _set_version_ticks(axes[0], vspecs, x_metric)
    _set_version_ticks(axes[1], vspecs, x_metric)
    axes[0].set_ylabel(f"Number of reefs (effective width >= {min_width_m:.0f} m)")
    axes[1].set_ylabel("Total area (km2)")
    axes[0].set_title("Reef count")
    axes[1].set_title("Reef area")
    for ax in axes:
        ax.grid(alpha=0.3)
    axes[0].legend(loc="upper left", fontsize=10)
    axes[1].legend(loc="upper left", fontsize=10)
    fig.suptitle("Total coral and rocky reef count and area by dataset version (North and North West Marine Regions) "
                 f"(effective width >= {min_width_m:.0f} m)")
    fig.tight_layout()
    out = os.path.abspath(os.path.join(FIG_DIR, filename))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    try:
        fig.savefig(out, dpi=150)
    except OSError as e:
        raise OSError(
            f"Failed to save figure to {out}: {e}\n"
            f"  Check that the directory exists and you have write permissions."
        )
    plt.close(fig)
    print(f"  Saved {out}")
    return out


def main():
    os.makedirs(FIG_DIR, exist_ok=True)
    os.makedirs(CACHE_DIR, exist_ok=True)

    print(f"Crosswalk: {CROSSWALK_CSV}")
    lookups = load_crosswalk()
    print(f"Coastline: {COASTLINE_FILE}")
    clip_land_module = load_clip_land_module()
    region_union = load_region_union()

    results = {}
    for vspec in VERSIONS:
        results[vspec["version"]] = process_version(
            vspec, lookups, clip_land_module, region_union
        )

    v12_spec = next(v for v in VERSIONS if v["version"] == "v1.2")
    check_v1_2(
        process_version(v12_spec, lookups, clip_land_module, apply_region=False)
    )

    countable = {}
    for vspec in VERSIONS:
        v = vspec["version"]
        print(f"\n=== {v}: countable reef clustering ===")
        countable[v] = cluster_countable(results[v], v)

    for vspec in VERSIONS:
        v = vspec["version"]
        print(f"\n=== {v}: size classification ===")
        results[v] = size_classify(results[v], version=v)

    table = build_table(results, SIZE_CLASSES)
    table.to_csv(TABLE_CSV, index=False)
    print(f"\nSaved table to {TABLE_CSV}")
    pd.set_option("display.width", 250)
    print(table.to_string(index=False))

    ctable = build_table(countable, COUNTABLE_SIZE_CLASSES)
    ctable.to_csv(COUNTABLE_TABLE_CSV, index=False)
    print(f"\nSaved countable table to {COUNTABLE_TABLE_CSV}")
    print(ctable.to_string(index=False))

    print("\nSaving figures...")
    # The standard >30 m count plots are replaced by the countable versions
    stale = os.path.join(FIG_DIR, "fig-fraction-counts.png")
    if os.path.exists(stale):
        os.remove(stale)
        print(f"  Removed {stale} (replaced by fig-countable-counts.png)")
    plot_fraction(
        ctable, "N", "fig-countable-counts.png",
        "Countable reef count by size class as a fraction of the v1.2 mapping "
        "(% of final v1.2 values; 50 m buffer clusters, effective width >= 100 m)",
        size_classes=COUNTABLE_SIZE_CLASSES,
    )
    plot_fraction(
        ctable, "Area_km2", "fig-countable-areas.png",
        "Countable reef area by size class as a fraction of the v1.2 mapping "
        "(% of final v1.2 values; 50 m buffer clusters, effective width >= 100 m)",
        size_classes=COUNTABLE_SIZE_CLASSES,
    )
    plot_fraction(
        table, "Area_km2", "fig-fraction-areas.png",
        "Reef area by size class as a fraction of the v1.2 mapping "
        "(% of final v1.2 values)",
    )
    out = plot_absolute(
        ctable, "fig-absolute.png",
        size_classes=COUNTABLE_SIZE_CLASSES, min_width_m=COUNTABLE_WIDTH_M,
    )
    print("\nDone.")


if __name__ == "__main__":
    main()
