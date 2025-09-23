"""
To assess the uncertainty in the mapping of the reef boundaries we need to use the
EdgeAcc_m attribute of each reef to simulate a distribution of possible reef boundaries. 
This will allow us to estiamte the uncertainty in counting of reefs when there is a size
and proximity threshold. This script is to check that our proposed dithered reef boundaries
result in a reef boundary distribution that is equivalent to a remapping of the reef boundaries.

To test this we will take the output of this script and pass it through V04a and V04b to verify
if the characteristics of the boundary error distributions are similar to the independent 
mapping of the reef boundaries, from v0-1 Rough Reef Mask.

In this script we load the v0-4 reef boundaries, then for each reef we apply a random buffer
based on the EdgeAcc_m attribute. The amount of buffering is based on a log-normal distribution
with a mu and sigma that is derived from matching the boundaries of the v0-1 Rough Reef Mask to 
the v04 reef boundaries. The calculation of mu and sigma is done in V04b-v0-4-analyse-match-lines.py.

The output of this script is a single shapefile with the dithered reef boundaries based on this
simple model. The goal of the script is to prove with this simple model that we can match the
characteristics of the boundary error distribution. 

The boundary error is a log-normal distribution that is an estimate between the single EdgeAcc_m 
attribute value associated with each reef feature and the 50th percentile error distance between
repeat mappings of the reefs. i.e. If I remap a reef then the boundary will change. If I measure
the distance between the two boundaries I can get a distribution of distances. The 50th percentile
of this distribution is the median distance between the two boundaries. To create a new simulated
boundary we take the EdgeAcc_m attribute then scale it by the Edge Accuracy to 50th percentile ratio
(edge_acc_ratio). The edge_acc_ratio is not a constant, but is sampled from a log-normal distribution
defined by MU and SIGMA below. The edge_acc_ratio is constrained to be between MIN_RATIO and MAX_RATIO.
This prevents extreme values that are not realistic. An edge_acc_ratio of 1.0 means that the EdgeAcc_m
is equal to the median error distance. An edge_acc_ratio close to zero 0 means that the EdgeAcc_m 
is much larger than that it should be and the simulated boundary will be very close to the 
original boundary.

For example if the EdgeAcc_m is 300 m and the sampled edge_acc_ratio is 0.5 then the median error 
distance is 150 m. This means that the new simulated boundary should be 150 m from the original boundary.
It could be positive or negative distance. For this we randomly choose to buffer in or out.

After buffering (and merging any touching reefs) the Area_km2 is recalculated. The applied buffer 
distance is recorded in the Buffer_m attribute.

When buffering results in overlapping polygons these are dissolved into a single polygon.
- EdgeAcc_m is retained as the maximum EdgeAcc_m of the combined reefs.
- Buffer_m is retained as the maximum Buffer_m of the combined reefs.
- Area_km2 is recalculated.
(Note: RB_Type_L1 is not required here; all features are treated as the same class for dissolution.)

Limitations:
In practice the boundary errors that occur are not buffers in or out, across the whole reef. In
practice the errors are more of a spatially correlated random walk along the boundary. The assumption
is that the simple buffering in and out of the whole reef will be sufficient to match the overall
error distribution when applied to enough reefs.

"""
# --- Implementation additions ---
import os
import sys
import numpy as np
import geopandas as gpd
from shapely.ops import unary_union
from shapely.geometry import Polygon, MultiPolygon

# Best fit between v0-1 Rough Reef Mask and v0-4 reef boundaries
MU = -0.57 
SIGMA = 0.852

MIN_RATIO = 0.05
MAX_RATIO = 2.0

DITHER_EDGE_ACC_RATIO = False  # if False use a fixed edge_acc_ratio. If False use Log-normal sampling. 
FIXED_EDGE_ACC_RATIO = 1.0

BASE_REEF_SHP = "working/V04a/NW-Aus-Feat_v0-4_RB_Type_L1_clip.shp"
OUTPUT_SHP = "working/V04c/NW-Aus-Feat_v0-4_RB_Type_L1_dithered.shp"

TARGET_CRS = "EPSG:3112"          # planar for buffering & area
RANDOM_SEED = 42                  # reproducibility
LOG_INTERVAL = 100                # progress logging

# Input / output (already defined above, keep constants as given)
# MU, SIGMA, MIN_RATIO, MAX_RATIO, BASE_REEF_SHP, OUTPUT_SHP already declared in header

def log_info(msg: str):
    print(f"[INFO] {msg}")

def log_warn(msg: str):
    print(f"[WARN] {msg}", file=sys.stderr)

def log_error(msg: str):
    print(f"[ERROR] {msg}", file=sys.stderr)

def sample_ratio() -> float:
    """Rejection sample a lognormal ratio within [MIN_RATIO, MAX_RATIO]."""
    if not DITHER_EDGE_ACC_RATIO:
        return FIXED_EDGE_ACC_RATIO
    for _ in range(10000):
        r = np.random.lognormal(mean=MU, sigma=SIGMA)
        if MIN_RATIO <= r <= MAX_RATIO:
            return r
    raise RuntimeError("Failed to sample ratio within bounds after many attempts.")

def ensure_singleparts(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Explode to ensure no multipart geometries."""
    return gdf.explode(index_parts=False, ignore_index=True)

def dissolve_touching_all(buffered_gdf: gpd.GeoDataFrame,
                          original_cols: list[str]) -> gpd.GeoDataFrame:
    """
    Dissolve ALL touching/overlapping polygons (single global class) into separate
    connected components. For each resulting component (polygon):
      EdgeAcc_m = max of members
      Buffer_m  = max of members
      Area_km2  recomputed later
      Other attributes:
         * If single unique value -> that value
         * Else -> semicolon-joined unique unique values
    """
    # Build global union (keeps disjoint parts as separate polygons inside MultiPolygon)
    union_geom = unary_union(buffered_gdf.geometry.values)
    if union_geom.is_empty:
        return gpd.GeoDataFrame(columns=original_cols, crs=buffered_gdf.crs)

    # Collect component polygons
    if isinstance(union_geom, Polygon):
        parts = [union_geom]
    elif isinstance(union_geom, MultiPolygon):
        parts = list(union_geom.geoms)
    else:
        parts = []

    # Prepare spatial join pieces
    parts_gdf = gpd.GeoDataFrame({"geometry": parts}, crs=buffered_gdf.crs)
    parts_gdf["comp_id"] = range(len(parts_gdf))

    join = gpd.sjoin(buffered_gdf, parts_gdf, predicate="intersects", how="inner")

    out_rows = []
    attr_cols = [c for c in original_cols if c != "geometry"]

    for cid, grp in join.groupby("comp_id"):
        comp_geom = parts_gdf.loc[parts_gdf["comp_id"] == cid, "geometry"].iloc[0]

        def agg_attr(col):
            if col in ("EdgeAcc_m", "Buffer_m", "Area_km2"):
                return None  # handled separately or recomputed
            vals = grp[col].dropna().unique().tolist()
            if not vals:
                return None
            if len(vals) == 1:
                return vals[0]
            return ";".join(sorted(str(v) for v in vals))

        row = {}
        for c in attr_cols:
            if c == "EdgeAcc_m":
                row[c] = float(grp["EdgeAcc_m"].max())
            elif c == "Buffer_m":
                row[c] = float(grp["Buffer_m"].max())
            elif c == "Area_km2":
                row[c] = None  # to be recalculated
            else:
                row[c] = agg_attr(c)
        row["geometry"] = comp_geom
        out_rows.append(row)

    return gpd.GeoDataFrame(out_rows, crs=buffered_gdf.crs)

def main():
    np.random.seed(RANDOM_SEED)

    if not os.path.exists(BASE_REEF_SHP):
        log_error(f"Input shapefile not found: {BASE_REEF_SHP}")
        sys.exit(1)

    log_info(f"Loading base reefs: {BASE_REEF_SHP}")
    base = gpd.read_file(BASE_REEF_SHP)
    if base.empty:
        log_error("Base reef layer is empty.")
        sys.exit(1)

    original_crs = base.crs
    log_info(f"Original CRS: {original_crs}")

    # Assertions
    assert "EdgeAcc_m" in base.columns, "EdgeAcc_m field missing."
    assert (base["EdgeAcc_m"] > 0).all(), "Found non-positive EdgeAcc_m values."

    original_columns = list(base.columns)  # preserve all
    # Project to planar CRS for buffering
    if str(base.crs) != TARGET_CRS:
        base_planar = base.to_crs(TARGET_CRS)
    else:
        base_planar = base

    # Buffer each feature
    buffered_records = []
    dropped_inward = 0
    for idx, row in base_planar.iterrows():
        geom = row.geometry
        edge_acc = float(row["EdgeAcc_m"])
        ratio = sample_ratio()
        buf_dist = edge_acc * ratio
        # Random sign (inward/outward)
        if np.random.rand() < 0.5:
            signed_dist = -buf_dist
        else:
            signed_dist = buf_dist
        try:
            new_geom = geom.buffer(signed_dist)
        except Exception:
            log_warn(f"Buffer failed for index {idx}; feature skipped.")
            continue
        if (new_geom is None) or new_geom.is_empty:
            # inward buffer completely removed geometry -> drop
            if signed_dist < 0:
                dropped_inward += 1
            continue
        rec = {c: row[c] for c in original_columns if c != "geometry"}
        rec["Buffer_m"] = signed_dist  # record applied (signed) buffer distance
        rec["geometry"] = new_geom
        buffered_records.append(rec)

        if (len(buffered_records) % LOG_INTERVAL) == 0:
            log_info(f"Buffered {len(buffered_records)} features (processed {idx+1}/{len(base_planar)})...")

    if not buffered_records:
        log_error("No buffered features produced.")
        sys.exit(1)

    buffered_gdf = gpd.GeoDataFrame(buffered_records, crs=base_planar.crs)

    # Ensure singlepart
    buffered_gdf = ensure_singleparts(buffered_gdf)
    log_info(f"Buffered features kept: {len(buffered_gdf)} (dropped inward removals: {dropped_inward})")

    # Dissolve touching features globally (no RB_Type_L1 dependency)
    log_info("Dissolving touching features (global)...")
    dissolved = dissolve_touching_all(buffered_gdf, buffered_gdf.columns.tolist())

    # Recalculate Area_km2 in planar CRS
    if "Area_km2" not in dissolved.columns:
        dissolved["Area_km2"] = None
    areas = dissolved.to_crs(TARGET_CRS).geometry.area / 1e6
    dissolved["Area_km2"] = areas

    # Reproject back to original CRS
    if str(dissolved.crs) != str(original_crs):
        dissolved_out = dissolved.to_crs(original_crs)
    else:
        dissolved_out = dissolved

    # Output
    out_dir = os.path.dirname(OUTPUT_SHP)
    os.makedirs(out_dir, exist_ok=True)

    # Overwrite
    if os.path.exists(OUTPUT_SHP):
        try:
            os.remove(OUTPUT_SHP)
        except Exception:
            pass

    log_info(f"Writing output: {OUTPUT_SHP}")
    dissolved_out.to_file(OUTPUT_SHP)

    # Summary stats
    ratios_abs = [abs(r["Buffer_m"]) / r["EdgeAcc_m"] for r in buffered_records if r["EdgeAcc_m"] > 0]
    log_info(f"Sampled ratio count: {len(ratios_abs)}  "
             f"mean={np.mean(ratios_abs):.3f}  median={np.median(ratios_abs):.3f}  "
             f"min={np.min(ratios_abs):.3f}  max={np.max(ratios_abs):.3f}")

    log_info("Done.")

if __name__ == "__main__":
    main()
