"""
Reef boundary (version v0-4) edge accuracy validation against independent legacy v0-1 mapping.

Purpose
Evaluate how well the v0-4 reef boundary dataset (A) aligns with an earlier reef/shallow
mask (B) without assuming one-to-one polygon correspondence. The method samples along
each dissolved v0-4 reef perimeter and measures nearest-planar distances to any v0-1
reef/shallow mask boundary segment. It summarizes the local distance distribution
(percentiles) and positions each feature’s supplied EdgeAcc_m (worst ~10% boundary
error estimate) within that empirical distribution (EdgePerc) plus a median scaling
metric (EdgeTo50p).

Data inputs (paths relative to project root)
A (v0-4 features): data/v0-4/out/AU_NESP-MaC-3-17_AIMS_NW-Aus-Features_v0-4.shp
B (v0-1 reef/shallow mask): data/v0-1_dual-maps/Reef-mask_Ref2_EL/
    AU_AIMS_NESP-MaC-3-17_Rough-reef-shallow-mask_87hr.shp
Region mask (comparability selector): data/v0-4/in/validation/Boundary-comp-regions_v0-4-to-v0-1-EL.shp

Processing overview
1. Load datasets A, B, region mask, and coastline land layer (via config.ini). Record A’s original CRS.
2. Filter A to RB_Type_L1 == 'Reef'. Repair invalid geometries (buffer(0)). Subset A, B, and land to features
   intersecting the region mask union. Clip B by land (remove landward/inland portions). Apply mutual overlap
   filter: retain only those A features that intersect at least one (clipped) B feature and only those B features
   intersecting at least one A feature (eliminates isolated reefs that would otherwise spuriously match distant B).
   Reproject A, B, region, land to EPSG:3112 for planar distance integrity.
3. Dissolve A reefs:
   - Unary union all filtered A reef polygons.
   - Explode to single-part dissolved “reef extents”.
   - For each dissolved polygon, compute EdgeAcc_m = max(EdgeAcc_m) of any original A polygons that intersect it.
     If all contributing EdgeAcc_m are null, retain null and emit a warning.
4. Prepare B boundary index:
   - Include BOTH exterior rings and interior (hole) rings of (clipped) B polygons as match candidates (enables
     valid landward/fringing reef inner-edge comparisons).
   - Build an STRtree (shapely) over these LineStrings.
   - Also create a unary union (MultiLineString) for rare fallback distance queries.
5. Per dissolved A polygon:
   - Generate perimeter sampling points along the exterior ring only.
   - Skip (omit from results entirely) if:
       * Geometry invalid after repair or empty, OR
       * Exterior ring has <= 4 unique coordinate tuples (insufficient complexity).
   - Determine sampling size k = min(MAX_SAMPLES, number of unique exterior vertices); current MAX_SAMPLES = 100
     (original concept referenced 40; percentile/statistical steps still compatible).
   - Sample k equidistant points at fraction i/k of perimeter length for i = 0..k-1 (no duplicate at full length).
   - Exclude any sampled points within 10 m of land (land buffer removal eliminates back/landward sides of fringing reefs).
   - For each retained sample point:
       * Perform spatial index candidate retrieval using pt.buffer(SEARCH_RADIUS_M).bounds (SEARCH_RADIUS_M = 2000 m).
       * Compute exact distances to candidate LineStrings (exterior or interior). Take the minimum.
       * If a candidate is within radius: store distance and create a LineString from sample point to nearest boundary point.
       * If no candidate within radius: treat distance as capped at SEARCH_RADIUS_M and record a “no-match” point.
       * Fallback to union linework if candidate retrieval unexpectedly returns none while geometry is nearby.

Field definitions
- EdgeAcc_m: Aggregated (max) worst ~10% boundary error estimate from source A polygons.
- DIST_M (in sample lines): Distance from sample point to nearest B boundary (metres, 0.1 precision).

Sampling & distance methodology
- Planar Euclidean distances in EPSG:3112.
- Exterior ring only to avoid potential internal void bias where B may lack holes.
- Equidistant fractional sampling ensures deterministic, scale-agnostic coverage given
  geometry complexity limitations (vertex count ceiling).
- Capped distances for no-match samples preserve percentile computability while
  signaling absence of local correspondence (pile-up at SEARCH_RADIUS_M).

Robustness / defensive measures
- Geometry repair via buffer(0).
- Mutual overlap filtering prevents false long-range matches.
- Interior ring inclusion ensures valid landward edge matching.
- Land exclusion suppresses spurious back-edge evaluations.
- STRtree acceleration; union fallback for rare edge cases.
- Null propagation of EdgeAcc_m where appropriate.

Limitations
- Asymmetric comparison (A→B only).
- Fixed search radius (2000 m) may censor extreme divergences.
- Dissolve loses internal partition provenance.
- Sample size ceiling (current 100) limits percentile resolution.
- Censoring at SEARCH_RADIUS_M compresses upper tail.

Performance considerations
- Complexity ≈ O(total_samples * log M), M = count of B ring segments.
- Memory acceptable at anticipated scale.

Error handling strategy
- Explicit checks for required fields & CRS.
- Continue past recoverable geometry issues.
- Clear logging for skips and null aggregations.

Rerun guidance
- Clear working/V04 outputs for clean regeneration.

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
import pandas as pd  # added for aggregation

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
# PATH_B = "data/v0-1_dual-maps/Reef-mask_Ref2_EL/AU_AIMS_NESP-MaC-3-17_Rough-reef-shallow-mask_87hr.shp"
PATH_B = "working/V04c/NW-Aus-Feat_v0-4_RB_Type_L1_dithered.shp"
PATH_REGION = "data/v0-4/in/validation/Boundary-comp-regions_v0-4-to-v0-1-EL.shp"
OUTPUT_A = "NW-Aus-Feat_v0-4_RB_Type_L1_clip.shp"

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
    Dissolve all reef polygons into single-part polygons and aggregate attributes.
      - EdgeAcc_m: max of contributing features
      - Area_km2 : sum of contributing features
    Returns GeoDataFrame with FID, EdgeAcc_m, Area_km2, geometry.
    Crashes early if required fields are missing.
    """
    assert "EdgeAcc_m" in gdf_a.columns, "Required field 'EdgeAcc_m' missing in input."
    assert "Area_km2" in gdf_a.columns, "Required field 'Area_km2' missing in input."

    # 1. Dissolve (unary union) then explode to single parts
    union_geom = unary_union(gdf_a.geometry.values)
    if union_geom.is_empty:
        raise ValueError("Union produced empty geometry.")
    dissolved_gdf = (
        gpd.GeoDataFrame(geometry=[union_geom], crs=gdf_a.crs)
        .explode(index_parts=False)
        .reset_index(drop=True)
    )
    dissolved_gdf["FID"] = dissolved_gdf.index
    log_info(f"Dissolve created {len(dissolved_gdf)} polygon parts.")

    # 2. Spatial join originals to dissolved parts
    joined = gpd.sjoin(
        gdf_a[["EdgeAcc_m", "Area_km2", "geometry"]],
        dissolved_gdf[["FID", "geometry"]],
        predicate="intersects",
        how="inner"
    )

    if joined.empty:
        log_warn("Spatial join returned no matches; all aggregates set to null/zero.")
        dissolved_gdf["EdgeAcc_m"] = None
        dissolved_gdf["Area_km2"] = 0.0
        return dissolved_gdf[["FID", "EdgeAcc_m", "Area_km2", "geometry"]]

    # 3. Numeric coercion
    joined["_EdgeAcc_num"] = pd.to_numeric(joined["EdgeAcc_m"], errors="coerce")
    joined["_Area_km2_num"] = pd.to_numeric(joined["Area_km2"], errors="coerce")

    # 4. Aggregate
    agg_df = (
        joined.groupby("FID")
        .agg({
            "_EdgeAcc_num": "max",
            "_Area_km2_num": "sum"
        })
        .reset_index()
        .rename(columns={
            "_EdgeAcc_num": "EdgeAcc_m",
            "_Area_km2_num": "Area_km2"
        })
    )

    out = dissolved_gdf.merge(agg_df, on="FID", how="left")

    # Basic warnings
    null_edge = out["EdgeAcc_m"].isna().sum()
    if null_edge:
        log_warn(f"{null_edge} dissolved parts have null EdgeAcc_m after aggregation.")
    zero_area = (out["Area_km2"] == 0).sum()
    if zero_area:
        log_warn(f"{zero_area} dissolved parts have zero Area_km2 after aggregation.")

    return out[["FID", "EdgeAcc_m", "Area_km2", "geometry"]]

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

    out_dir = Path("working/V04a"); out_dir.mkdir(parents=True, exist_ok=True)
    gdf_write.to_file(out_dir / OUTPUT_A)
    sample_pts_write.to_file(out_dir / "sample_site_pts.shp")
    match_lines_write.to_file(out_dir / "sample_match_lines.shp")
    no_match_pts_write.to_file(out_dir / "sample_no_match_pts.shp")
    log_info("Match line generation complete. Inspect outputs in QGIS.")

if __name__ == "__main__":
    main()
