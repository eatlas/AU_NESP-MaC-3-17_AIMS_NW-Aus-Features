"""
Reef boundary (version v0-4) edge accuracy validation against legacy v0-1 mapping.

Purpose
Evaluate how well the v0-4 reef boundary dataset (A) aligns with an earlier reef/shallow
mask (B) without assuming one-to-one polygon correspondence. The method samples along
each dissolved v0-4 reef perimeter and measures nearest-planar distances to any v0-1
reef/shallow mask boundary segment. It summarizes the local distance distribution
(percentiles) and positions each feature’s supplied EdgeAcc_m (worst ~10% boundary
error estimate) within that empirical distribution (EdgePerc) plus a median scaling
metric (EdgeTo50p).

Data inputs (paths relative to project root)
A (v0-4 features): data\\v0-4\\out\\AU_NESP-MaC-3-17_AIMS_NW-Aus-Features_v0-4.shp
B (v0-1 reef/shallow mask): data\\v0-1_dual-maps\\Reef-mask_Ref2_EL\\
    AU_AIMS_NESP-MaC-3-17_Rough-reef-shallow-mask_87hr.shp
Region mask (comparability selector): data\\v0-4\\in\\validation\\Boundary-comp-regions_v0-4-to-v0-1-EL.shp

Core assumptions
- Neither dataset is definitive ground truth; A supplies feature-level EdgeAcc_m estimates.
- Only A features with RB_Type_L1 == 'Reef' are evaluated.
- Region mask acts only as a spatial selector (intersects test); geometries are not clipped.
- Comparison is many-to-many tolerant of splits/merges between versions.
- Only exterior perimeters are sampled (holes ignored).
- Distances are one-way (A→B); no reciprocal B→A analysis.

Library / environment (confirmed available)
- Python 3.13.1
- geopandas 1.0.1
- shapely 2.0.7
- numpy, pandas
- fiona 1.10.1
- GDAL 3.10.2
- matplotlib 3.9.x (for plots)

Processing overview
1. Load datasets A, B, and the region mask; record A’s original CRS. Reproject all
   working geometries to EPSG:3112 (metres) for planar distance integrity.
2. Filter A to RB_Type_L1 == 'Reef'. Build region union; retain (do not clip) only
   those A and B features whose geometries intersect the region union.
3. Dissolve A reefs:
   - Unary union all filtered A reef polygons.
   - Explode to singlepart dissolved “reef extents”.
   - For each dissolved polygon, compute EdgeAcc_m = max(EdgeAcc_m) of any original
     A polygons that intersect it (after a validity repair via buffer(0) if needed).
     If all contributing EdgeAcc_m are null, retain null and emit a warning.
4. Prepare B boundary index:
   - Explode multipart polygons to singlepart.
   - Extract exterior AND interior (hole) rings as LineStrings (both are valid match targets).
   - Build an STRtree (shapely) over these LineStrings.
   - Also create a unary union (MultiLineString) for rare fallback distance queries.
5. Per dissolved A polygon:
   - Skip (omit from results entirely) if:
       * Geometry invalid after repair or empty, OR
       * Exterior ring has <= 4 unique coordinate tuples (insufficient complexity).
   - Determine sampling size k = min(MAX_SAMPLES, number of unique exterior vertices),
     with MAX_SAMPLES = 40.
   - Sample k equidistant points along exterior at fraction i/k of perimeter length
     for i = 0..k-1 (start point included once; no duplicate at full length).
   - For each sample point:
       * Perform spatial index candidate retrieval using a bounding box of
         point.buffer(SEARCH_RADIUS_M).bounds (SEARCH_RADIUS_M = 2000 m).
       * Compute exact distances to candidate LineStrings; take the minimum.
       * If any candidate within radius: store distance and create a LineString
         from sample point to the nearest point on that candidate boundary.
       * If no candidate within radius: treat distance as capped at SEARCH_RADIUS_M,
         record a “no-match” point (no line stored).
       * In edge cases of empty candidate return where nearby geometry exists,
         fall back to distance against the union linework.
6. Distance statistics per dissolved A polygon:
   - Collect all k distances (with capped values included for no-matches).
   - Compute percentiles p05, p10, p15, ..., p95, p100 (increments of 5) using
     numpy.percentile with linear interpolation (default method); round each to
     0.1 m: round(value, 1).
   - EdgePerc: Percentile rank (0–100) of EdgeAcc_m within the sampled distance
     distribution by linear interpolation over the sorted distances and their
     associated empirical percentile positions; round to 0.1. If EdgeAcc_m is
     null → EdgePerc null. If EdgeAcc_m exceeds all observed distances → 100.0.
   - EdgeTo50p: Ratio p50 / EdgeAcc_m when EdgeAcc_m > 0 and p50 present; else null.
     (Stored unrounded or optionally rounded to 4 decimals—will implement 4-decimal
     rounding for readability.)
7. Output features (only for non-skipped dissolved polygons) include attributes:
     EdgeAcc_m
     p05, p10, p15, ..., p95, p100
     EdgePerc
     EdgeTo50p
8. Write dissolved polygon output shapefile:
     working\\V04\\Reef_EdgeAcc_Comparison.shp
   Reproject results back to the original CRS of dataset A before write.
9. Diagnostic / supplementary outputs:
   - Matched sample lines: working\\V04\\Reef_EdgeAcc_SampleLines.shp
       Fields:
         FID   (integer index of dissolved polygon feature)
         SID   (sample index 0..k-1)
         DIST_M (measured distance in metres, float, 0.1 m rounding applied)
       Geometry: LineString from sampled A boundary point to nearest B boundary point.
       (EDGEACC intentionally omitted per clarified spec.)
   - No-match sample points: working\\V04\\Reef_EdgeAcc_NoMatchPts.shp
       Fields:
         FID
         SID
       Geometry: Point (original sample location) with no B boundary within radius.
10. Plots (log-log scale):
    - EdgeAcc_m vs p50 and p90 (two series): EdgeAcc_vs_p50_p90.png
    - EdgeAcc_m vs EdgeTo50p: EdgeAcc_vs_EdgeTo50p.png
11. Logging:
    - Progress message every LOG_INTERVAL (50) dissolved polygons.
    - Additional debug tracing (geometry summary, first few sample distances)
      for the first DEBUG_FEATURES (3) dissolved polygons.

Field definitions
- EdgeAcc_m: Aggregated (max) worst ~10% boundary error estimate from source A polygons.
- pXX: Empirical distance percentiles (metres, rounded to 0.1).
- EdgePerc: Percentile rank position (0–100) of EdgeAcc_m among sampled distances (0.1 precision).
- EdgeTo50p: p50 / EdgeAcc_m (dimensionless scalar); >1 implies EdgeAcc_m underestimates median discrepancy.
- DIST_M (in sample lines): Distance from sample point to nearest B boundary (metres, 0.1 precision).

Sampling & distance methodology
- Planar Euclidean distances in EPSG:3112.
- Exterior ring only to avoid potential internal void bias where B may lack holes.
- Equidistant fractional sampling ensures deterministic, scale-agnostic coverage given
  geometry complexity limitations (vertex count ceiling).
- Capped distances for no-match samples preserve percentile computability while
  signaling absence of local correspondence (pile-up at SEARCH_RADIUS_M).

Robustness / defensive measures
- Repair invalid geometries via buffer(0); skip if still invalid/empty (no output row).
- Skip overly simple perimeters (<=4 unique vertices) to avoid degenerate statistics.
- STRtree usage tolerant of shapely 2.x return types (geometry objects).
- Fallback to union linework distance if an unexpected empty candidate set occurs.
- Null EdgeAcc_m values propagate; EdgePerc and EdgeTo50p become null accordingly.
- Handles moderate dataset size (≈1000 dissolved polygons post-filter) in memory.

Limitations
- Asymmetric comparison (A→B only); discrepancies where B extends beyond A are not evaluated reciprocally.
- Search radius fixed (2000 m) may saturate distances in areas of extreme divergence.
- Dissolve eliminates internal partition provenance; evaluation is at aggregated reef extent level.
- Percentile resolution limited by sample size (≤40).
- Capping introduces an upper-tail compression; interpretation should consider potential censoring at SEARCH_RADIUS_M.

Performance considerations
- Complexity roughly O(total_samples * log M) with spatial indexing (M = count of B boundary segments).
- Sample size constrained (≤40 per polygon) for tractable, uniform runtime.
- Unary union operations acceptable at described scale.

Error handling strategy
- Raise or log critical errors on missing required fields (e.g., RB_Type_L1, EdgeAcc_m presence).
- Continue past individual polygon anomalies (skips) without aborting batch.
- Clear messaging for skipped polygons (invalid / too simple).

Key constants (to be defined near top in implementation)
  SEARCH_RADIUS_M = 2000
  MAX_SAMPLES = 40
  LOG_INTERVAL = 50
  DEBUG_FEATURES = 3
  PERCENTILES = [5,10,15,20,25,30,35,40,45,50,55,60,65,70,75,80,85,90,95,100]

Rerun guidance
- Remove or archive existing outputs in working\\V04 before regeneration for a clean run.
- Adjust SEARCH_RADIUS_M or MAX_SAMPLES constants for sensitivity analyses if needed.
- Re-run end-to-end to ensure derived plots and diagnostic layers stay consistent.

Planned implementation structure (forthcoming)
- main() orchestration
- load_and_prepare() for inputs & CRS
- dissolve_and_aggregate_edgeacc()
- build_b_boundary_index()
- sample_and_measure_distances()
- compute_statistics()
- write_outputs()
- generate_plots()
- Utility helpers: percentile_rank(), safe_buffer0(), log_progress()
"""
from __future__ import annotations

import sys
from typing import Tuple, Optional
from pathlib import Path  # added
import geopandas as gpd
from shapely.geometry import base, Polygon, MultiPolygon, GeometryCollection  # extended
from shapely.ops import unary_union
from shapely.strtree import STRtree  # added
from shapely.geometry import LineString, Point, MultiLineString  # added
from shapely.ops import nearest_points  # added
import numpy as np  # added
import configparser  # added

# ---------------------------------------------------------------------------
# Constants (Phase 0)
# ---------------------------------------------------------------------------
TARGET_CRS = "EPSG:3112"
SEARCH_RADIUS_M = 2000
MAX_SAMPLES = 100
LOG_INTERVAL = 50
DEBUG_FEATURES = 3
PERCENTILES = [5,10,15,20,25,30,35,40,45,50,55,60,65,70,75,80,85,90,95,100]
LAND_BUFFER_M = 10  # new

# Paths now relative to current working directory (no project_root resolution)
PATH_A = "data/v0-4/out/AU_NESP-MaC-3-17_AIMS_NW-Aus-Features_v0-4.shp"
PATH_B = "data/v0-1_dual-maps/Reef-mask_Ref2_EL/AU_AIMS_NESP-MaC-3-17_Rough-reef-shallow-mask_87hr.shp"
PATH_REGION = "data/v0-4/in/validation/Boundary-comp-regions_v0-4-to-v0-1-EL.shp"

# ---------------------------------------------------------------------------
# Lightweight logging helpers
# ---------------------------------------------------------------------------
def log_info(msg: str) -> None:
    print(f"[INFO] {msg}")

def log_warn(msg: str) -> None:
    print(f"[WARN] {msg}", file=sys.stderr)

def log_error(msg: str) -> None:
    print(f"[ERROR] {msg}", file=sys.stderr)

# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------
def safe_buffer0(geom: base.BaseGeometry) -> Optional[base.BaseGeometry]:
    """Attempt validity repair with buffer(0). Return repaired geometry or None if invalid/empty."""
    if geom is None or geom.is_empty:
        return None
    try:
        if not geom.is_valid:
            geom = geom.buffer(0)
        if geom.is_empty:
            return None
        return geom
    except Exception:
        return None

def repair_geometries(gdf: gpd.GeoDataFrame, label: str) -> gpd.GeoDataFrame:
    """Repair invalid geometries; drop empties."""
    original_count = len(gdf)
    gdf = gdf.copy()
    gdf["geometry"] = gdf["geometry"].apply(safe_buffer0)
    gdf = gdf[~gdf.geometry.isna() & ~gdf.geometry.is_empty]
    repaired_count = len(gdf)
    dropped = original_count - repaired_count
    if dropped:
        log_warn(f"{label}: dropped {dropped} invalid/empty geometries after repair (kept {repaired_count}).")
    return gdf

# ---------------------------------------------------------------------------
# Core loading & preparation (Phase 1)
# ---------------------------------------------------------------------------
def load_and_prepare() -> Tuple[gpd.GeoDataFrame, gpd.GeoDataFrame, gpd.GeoDataFrame, gpd.GeoDataFrame, str]:
    """
    Load shapefiles A, B, region mask, and land.
    Steps:
      - Read A, B, region mask.
      - Read config.ini to locate land shapefile; load land.
      - Repair geometries (buffer(0)).
      - Filter A to RB_Type_L1 == 'Reef'.
      - Subset A, B, LAND by intersection with region mask union (no clipping yet).
      - Clip B by land (remove landward areas): B := B - land_union (drop empties).
      - Mutually retain only A features intersecting B and B features intersecting A (post-clip).
      - Reproject all (A,B,region,land) to TARGET_CRS.
    Returns: (gdf_a, gdf_b_clipped, gdf_region, land_subset, original_crs)
    """
    log_info(f"Loading A: {PATH_A}")
    gdf_a = gpd.read_file(PATH_A)
    log_info(f"Loading B: {PATH_B}")
    gdf_b = gpd.read_file(PATH_B)
    log_info(f"Loading Region mask: {PATH_REGION}")
    gdf_region = gpd.read_file(PATH_REGION)

    if gdf_a.crs is None:
        raise ValueError("Dataset A has no CRS defined.")
    original_crs = gdf_a.crs
    if "RB_Type_L1" not in gdf_a.columns:
        raise KeyError("Dataset A missing required field 'RB_Type_L1'.")

    # Load land from config
    cfg = configparser.ConfigParser()
    if not cfg.read("config.ini"):
        raise FileNotFoundError("config.ini missing or unreadable.")
    base_path = cfg.get("general", "in_3p_path")
    land_file = f"{base_path}/AU_AIMS_Coastline_50k_2024/Split/AU_NESP-MaC-3-17_AIMS_Aus-Coastline-50k_2024_V1-1_split.shp"
    log_info(f"Loading Land: {land_file}")
    land_gdf = gpd.read_file(land_file)

    # Filter A to reefs
    pre_a = len(gdf_a)
    gdf_a = gdf_a[gdf_a["RB_Type_L1"] == "Reef"].copy()
    log_info(f"A reef filter: {pre_a} -> {len(gdf_a)}")

    # Repair geometries
    gdf_a = repair_geometries(gdf_a, "A")
    gdf_b = repair_geometries(gdf_b, "B")
    gdf_region = repair_geometries(gdf_region, "Region")
    land_gdf = repair_geometries(land_gdf, "Land")

    if gdf_region.empty:
        raise ValueError("Region mask empty after repair.")
    if land_gdf.empty:
        log_warn("Land dataset empty after repair; B clipping will be skipped.")

    # Ensure common CRS (use region CRS)
    region_crs = gdf_region.crs
    for gdf_ref, label in [(gdf_a, "A"), (gdf_b, "B"), (land_gdf, "Land")]:
        if gdf_ref.crs != region_crs:
            if label == "A":
                gdf_a = gdf_a.to_crs(region_crs)
            elif label == "B":
                gdf_b = gdf_b.to_crs(region_crs)
            else:
                land_gdf = land_gdf.to_crs(region_crs)

    # Subset by region mask intersection
    region_union = unary_union(gdf_region.geometry.values)
    a_before = len(gdf_a); b_before = len(gdf_b); land_before = len(land_gdf)
    gdf_a = gdf_a[gdf_a.intersects(region_union)].copy()
    gdf_b = gdf_b[gdf_b.intersects(region_union)].copy()
    land_gdf = land_gdf[land_gdf.intersects(region_union)].copy()
    log_info(f"A region select: {a_before} -> {len(gdf_a)}")
    log_info(f"B region select: {b_before} -> {len(gdf_b)}")
    log_info(f"Land region select: {land_before} -> {len(land_gdf)}")

    # Clip B by land (remove landward areas)
    if not land_gdf.empty and not gdf_b.empty:
        land_union = unary_union(land_gdf.geometry.values)
        if not land_union.is_empty:
            clipped_geoms = []
            removed = 0
            for geom in gdf_b.geometry:
                if geom.intersects(land_union):
                    diff = geom.difference(land_union)
                    if diff.is_empty:
                        removed += 1
                        continue
                    clipped_geoms.append(diff)
                else:
                    clipped_geoms.append(geom)
            gdf_b = gdf_b.iloc[0:0].assign(geometry=clipped_geoms) if clipped_geoms else gdf_b.iloc[0:0]
            gdf_b = gpd.GeoDataFrame(gdf_b, geometry="geometry", crs=region_crs)
            log_info(f"B clipping by land complete: removed {removed} fully land-overlapped polygons; kept {len(gdf_b)}")
        else:
            log_warn("Land union empty; skipping B clipping.")
    else:
        log_warn("Skipping B clipping (empty land or B).")

    # --- Debug: write clipped B shapefile ---
    try:
        debug_dir = Path("working/V04")
        debug_dir.mkdir(parents=True, exist_ok=True)
        debug_path = debug_dir / "debug_B_clipped.shp"
        gdf_b.to_file(debug_path)
        log_info(f"Debug: wrote clipped B shapefile to {debug_path}")
    except Exception as e:
        log_warn(f"Failed to write debug B clipped shapefile: {e}")

    # Mutual intersection filter (post-clip)
    a_pre_overlap = len(gdf_a); b_pre_overlap = len(gdf_b)
    if not gdf_a.empty and not gdf_b.empty:
        gdf_a = gdf_a.reset_index(drop=True)
        gdf_b = gdf_b.reset_index(drop=True)
        overlap_pairs = gpd.sjoin(gdf_a[["geometry"]], gdf_b[["geometry"]], predicate="intersects", how="inner")
        if overlap_pairs.empty:
            log_warn("No mutual intersections after clipping; datasets become empty.")
            gdf_a = gdf_a.iloc[0:0]; gdf_b = gdf_b.iloc[0:0]
        else:
            a_keep = overlap_pairs.index.unique()
            b_keep = overlap_pairs["index_right"].unique()
            gdf_a = gdf_a.loc[a_keep].copy()
            gdf_b = gdf_b.loc[b_keep].copy()
            log_info(f"Mutual overlap filter: A {a_pre_overlap} -> {len(gdf_a)}, B {b_pre_overlap} -> {len(gdf_b)}")
    else:
        log_warn("Skipped mutual overlap filter (A or B empty).")

    # Reproject to target CRS
    if region_crs != TARGET_CRS:
        if not gdf_a.empty: gdf_a = gdf_a.to_crs(TARGET_CRS)
        if not gdf_b.empty: gdf_b = gdf_b.to_crs(TARGET_CRS)
        gdf_region = gdf_region.to_crs(TARGET_CRS)
        if not land_gdf.empty: land_gdf = land_gdf.to_crs(TARGET_CRS)

    log_info("Reprojection complete.")
    return gdf_a, gdf_b, gdf_region, land_gdf, str(original_crs)

# ---------------------------------------------------------------------------
# Simplified dissolve & aggregate EdgeAcc (current)
# ---------------------------------------------------------------------------
def dissolve_and_aggregate_edgeacc(gdf_a: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Simplified dissolve:
      1) Unary union then explode to single-part polygons.
      2) Spatial join original features to parts (intersects).
      3) Group by part id to compute max EdgeAcc_m (if present).
    Returns GeoDataFrame with FID, EdgeAcc_m, geometry.
    """
    has_edgeacc = "EdgeAcc_m" in gdf_a.columns
    if not has_edgeacc:
        log_warn("Source A missing 'EdgeAcc_m'; aggregated result will contain nulls.")

    # 1. Dissolve all reef polygons, explode to single parts
    union_geom = unary_union(gdf_a.geometry.values)
    if union_geom.is_empty:
        raise ValueError("Union produced empty geometry.")
    dissolved_gdf = gpd.GeoDataFrame(geometry=[union_geom], crs=gdf_a.crs).explode(index_parts=False).reset_index(drop=True)
    dissolved_gdf["FID"] = dissolved_gdf.index  # stable id
    log_info(f"Dissolve created {len(dissolved_gdf)} polygon parts.")

    # 2. Spatial join original polygons to dissolved parts
    # (intersects predicate; we only need matching polygons)
    joined = gpd.sjoin(
        gdf_a[["EdgeAcc_m", "geometry"]] if has_edgeacc else gdf_a[["geometry"]],
        dissolved_gdf[["FID", "geometry"]],
        predicate="intersects",
        how="inner"
    )

    if joined.empty:
        log_warn("Spatial join returned no matches; all EdgeAcc_m will be null.")
        dissolved_gdf["EdgeAcc_m"] = None
        return dissolved_gdf[["FID", "EdgeAcc_m", "geometry"]]

    # 3. Aggregate max EdgeAcc_m per FID
    if has_edgeacc:
        # Coerce numeric, ignore non-numeric
        joined["_EdgeAcc_num"] = (
            joined["EdgeAcc_m"]
            .apply(lambda v: float(v) if v is not None and str(v).strip() != "" else None)
        )
        agg = (
            joined.groupby("FID")["_EdgeAcc_num"]
            .max()
            .rename("EdgeAcc_m")
            .to_frame()
            .reset_index()
        )
    else:
        agg = dissolved_gdf[["FID"]].copy()
        agg["EdgeAcc_m"] = None

    # Merge back
    out = dissolved_gdf.merge(agg, on="FID", how="left")
    # Warn on null EdgeAcc_m where source polygons existed
    if has_edgeacc:
        null_count = out["EdgeAcc_m"].isna().sum()
        if null_count:
            log_warn(f"{null_count} dissolved parts have null EdgeAcc_m (all contributing values null or non-numeric).")

    return out[["FID", "EdgeAcc_m", "geometry"]]

# ---------------------------------------------------------------------------
# Perimeter sampling (Phase 3 - points only, no distances to B yet)
# ---------------------------------------------------------------------------
def generate_sampling_points(gdf_dissolved: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    For each dissolved polygon:
      - Skip if exterior has <=4 unique vertices or zero length.
      - Sample k = min(MAX_SAMPLES, unique_vertex_count) equidistant points
        along the exterior at fractions i/k (i=0..k-1) of perimeter length.
      - Do not duplicate the start point at full length.
    Returns GeoDataFrame with fields: FID, SID, geometry (Point).
    """
    records = []
    skipped = 0
    for _, row in gdf_dissolved.iterrows():
        fid = row["FID"]
        geom = row.geometry
        if geom is None or geom.is_empty:
            skipped += 1
            continue
        exterior = geom.exterior
        if exterior is None:
            skipped += 1
            continue
        coords = list(exterior.coords)
        if len(coords) < 2:
            skipped += 1
            continue
        # Remove duplicate closing coord for uniqueness test
        if coords[0] == coords[-1]:
            coords_core = coords[:-1]
        else:
            coords_core = coords
        unique_vertices = { (x, y) for x, y, *rest in ( (c[0], c[1]) for c in coords_core ) }
        n_unique = len(unique_vertices)
        if n_unique <= 4:
            skipped += 1
            continue
        length = exterior.length
        if length <= 0:
            skipped += 1
            continue
        k = min(MAX_SAMPLES, n_unique)
        for sid in range(k):
            dist = (length * sid) / k
            pt = exterior.interpolate(dist)
            records.append({"FID": fid, "SID": sid, "geometry": pt})
    log_info(f"Sampling: created {len(records)} points (skipped {skipped} polygons with insufficient complexity).")
    return gpd.GeoDataFrame(records, geometry="geometry", crs=gdf_dissolved.crs)

# ---------------------------------------------------------------------------
# Filter sample points near land (Phase 3b)
# ---------------------------------------------------------------------------
def filter_sample_points_near_land(sample_pts: gpd.GeoDataFrame,
                                   region_mask: gpd.GeoDataFrame,
                                   land_gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Removes sample points within LAND_BUFFER_M of land (land_gdf already loaded & region-subset).
    land_gdf assumed in same CRS as sample_pts.
    """
    if land_gdf.empty:
        log_warn("Land GeoDataFrame empty; skipping land proximity filter.")
        return sample_pts

    land_union = unary_union(land_gdf.geometry.values)
    if land_union.is_empty:
        log_warn("Land union empty; skipping land proximity filter.")
        return sample_pts
    land_buffer = land_union.buffer(LAND_BUFFER_M)

    sidx = sample_pts.sindex
    candidate_idx = list(sidx.intersection(land_buffer.bounds))
    if not candidate_idx:
        log_info("Land filter: no candidate sample points in buffer bbox.")
        return sample_pts

    cand_pts = sample_pts.iloc[candidate_idx]
    remove_ids = set(cand_pts.index[cand_pts.intersects(land_buffer)])
    if not remove_ids:
        log_info("Land filter: no points within buffer; none removed.")
        return sample_pts

    filtered = sample_pts[~sample_pts.index.isin(remove_ids)].copy()
    log_info(f"Land filter: removed {len(remove_ids)} / {len(sample_pts)} points within {LAND_BUFFER_M} m of land.")
    return filtered

# ---------------------------------------------------------------------------
# B boundary extraction & index (Phase 4 prep)
# ---------------------------------------------------------------------------
def extract_b_boundaries(gdf_b: gpd.GeoDataFrame):
    """
    Return (list_of_line_geoms, STRtree_index, union_multiline) for B polygon rings.
    Includes both exterior rings and interior (hole) rings so inner reef / island-edge
    sample points can match to landward reef boundaries.
    """
    line_geoms = []
    for geom in gdf_b.geometry:
        if geom is None or geom.is_empty:
            continue
        polys = getattr(geom, "geoms", [geom])  # handle MultiPolygon
        for p in polys:
            # Exterior
            ext = getattr(p, "exterior", None)
            if ext:
                line_geoms.append(LineString(ext.coords))
            # Interiors (holes)
            for interior in getattr(p, "interiors", []):
                if interior and len(interior.coords) > 2:
                    line_geoms.append(LineString(interior.coords))
    if not line_geoms:
        raise ValueError("No polygon rings (exterior/interior) extracted from B.")
    tree = STRtree(line_geoms)
    union_ml = MultiLineString([lg for lg in line_geoms])
    return line_geoms, tree, union_ml

# ---------------------------------------------------------------------------
# Generate match lines (Phase 4 - distances & no-match points)
# ---------------------------------------------------------------------------
def generate_match_lines(sample_pts: gpd.GeoDataFrame,
                         gdf_b: gpd.GeoDataFrame) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    """
    For each sample point:
      - Find nearest B boundary within SEARCH_RADIUS_M.
      - If found: create LineString (sample -> nearest point) with DIST_M (0.1 m rounding).
      - If none within radius: record point in no-match output.
    Handles STRtree query returning either geometries or integer indices.
    Returns (lines_gdf, no_match_pts_gdf).
    """
    line_geoms, tree, union_ml = extract_b_boundaries(gdf_b)
    # Pre-map id(geom) -> geom index for geometry-return mode
    id_to_idx = {id(g): i for i, g in enumerate(line_geoms)}

    lines_out = []
    no_match = []
    total = len(sample_pts)

    for i, row in sample_pts.iterrows():
        pt: Point = row.geometry
        fid = row["FID"]
        sid = row["SID"]

        # Candidate query: use radius buffer envelope to reduce candidate set
        search_env = pt.buffer(SEARCH_RADIUS_M).envelope
        candidates = tree.query(search_env)

        min_dist = None
        nearest_pt_on_line = None

        if candidates is not None and len(candidates) > 0:
            for cand in candidates:
                # Normalize candidate to geometry
                if isinstance(cand, (int, np.integer)):
                    geom_c = line_geoms[int(cand)]
                else:
                    geom_c = cand
                    # (Optional) guard if object identity not in map; ignore if not LineString-like
                    if not hasattr(geom_c, "distance"):
                        continue
                d = pt.distance(geom_c)
                if d <= SEARCH_RADIUS_M and (min_dist is None or d < min_dist):
                    # Compute nearest point only when we have a better candidate
                    _, npt = nearest_points(pt, geom_c)
                    min_dist = d
                    nearest_pt_on_line = npt

        # Fallback to union if still no candidate within radius
        if min_dist is None:
            d_union = pt.distance(union_ml)
            if d_union <= SEARCH_RADIUS_M:
                min_dist = d_union
                _, nearest_pt_on_line = nearest_points(pt, union_ml)

        if min_dist is None:
            no_match.append({"FID": fid, "SID": sid, "geometry": pt})
        else:
            lines_out.append({
                "FID": fid,
                "SID": sid,
                "DIST_M": round(min_dist, 1),
                "geometry": LineString([pt, nearest_pt_on_line])
            })

        if (i + 1) % 10000 == 0:
            log_info(f"Processed {i+1}/{total} sample points...")

    log_info(f"Matching complete: {len(lines_out)} matched, {len(no_match)} no-match (radius {SEARCH_RADIUS_M} m).")
    lines_gdf = gpd.GeoDataFrame(lines_out, geometry="geometry", crs=sample_pts.crs)
    nomatch_gdf = gpd.GeoDataFrame(no_match, geometry="geometry", crs=sample_pts.crs)
    return lines_gdf, nomatch_gdf

# ---------------------------------------------------------------------------
# Main entry (Phase 1 reporting only)
# ---------------------------------------------------------------------------
def main():
    try:
        gdf_a, gdf_b, gdf_region, land_gdf, orig_crs = load_and_prepare()
    except Exception as e:
        log_error(f"Failed during load_and_prepare: {e}")
        sys.exit(1)

    log_info("=== Preparation Summary ===")
    log_info(f"Original CRS (A): {orig_crs}")
    log_info(f"Working CRS: {gdf_a.crs}")
    log_info(f"Filtered A reef features: {len(gdf_a)}")
    log_info(f"Filtered & clipped B features: {len(gdf_b)}")
    log_info(f"Region mask polygons: {len(gdf_region)}")
    log_info(f"Land polygons (subset): {len(land_gdf)}")

    gdf_dissolved = dissolve_and_aggregate_edgeacc(gdf_a)
    sample_pts = generate_sampling_points(gdf_dissolved)
    sample_pts = filter_sample_points_near_land(sample_pts, gdf_region, land_gdf)
    match_lines, no_match_pts = generate_match_lines(sample_pts, gdf_b)

    if str(gdf_dissolved.crs) != str(orig_crs):
        gdf_write = gdf_dissolved.to_crs(orig_crs)
        sample_pts_write = sample_pts.to_crs(orig_crs)
        match_lines_write = match_lines.to_crs(orig_crs)
        no_match_pts_write = no_match_pts.to_crs(orig_crs)
    else:
        gdf_write = gdf_dissolved
        sample_pts_write = sample_pts
        match_lines_write = match_lines
        no_match_pts_write = no_match_pts

    out_dir = Path("working/V04"); out_dir.mkdir(parents=True, exist_ok=True)
    gdf_write.to_file(out_dir / "dissolve_and_aggregate.shp")
    sample_pts_write.to_file(out_dir / "sample_site_pts.shp")
    match_lines_write.to_file(out_dir / "sample_match_lines.shp")
    no_match_pts_write.to_file(out_dir / "sample_no_match_pts.shp")
    log_info("Match line generation complete. Inspect outputs in QGIS.")

if __name__ == "__main__":
    main()


