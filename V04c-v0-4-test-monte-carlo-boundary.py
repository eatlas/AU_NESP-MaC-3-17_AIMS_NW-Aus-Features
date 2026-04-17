"""
To assess the uncertainty in the mapping of the reef boundaries we need to use the
EdgeAcc_m attribute of each reef to simulate a distribution of possible reef boundaries.
This will allow us to estimate the uncertainty in counting of reefs when there is a size
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
is equal to the median error distance. An edge_acc_ratio close to 0 means that the EdgeAcc_m
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

DITHER_EDGE_ACC_RATIO = True  # if False use a fixed edge_acc_ratio. If False use Log-normal sampling.
FIXED_EDGE_ACC_RATIO = 1.0

BASE_REEF_SHP = "working/V04a/NW-Aus-Feat_v0-4_RB_Type_L1_clip.shp"
OUTPUT_SHP = "working/V04c/NW-Aus-Feat_v0-4_RB_Type_L1_dithered.shp"

TARGET_CRS = "EPSG:3112"          # planar for buffering & area
RANDOM_SEED = 42                  # reproducibility
LOG_INTERVAL = 100                # progress logging

# Input / output (already defined above, keep constants as given)
# MU, SIGMA, MIN_RATIO, MAX_RATIO, BASE_REEF_SHP, OUTPUT_SHP already declared in header

def generate_dithered_boundaries(
    base_gdf: gpd.GeoDataFrame,
    mu: float,
    sigma: float,
    min_ratio: float,
    max_ratio: float,
    use_lognormal: bool = True,
    fixed_ratio: float = 1.0,
    max_attempts: int = 10000,
    log_interval: int = 100,
    edge_acc_field: str = "EdgeAcc_m",
    buffer_field: str = "Buffer_m",
    area_field: str = "Area_km2",
) -> gpd.GeoDataFrame:
    """Generate a dithered (simulated) reef boundary layer based on per-feature edge accuracy.

    Parameters
    ----------
    base_gdf : GeoDataFrame
        Input reef boundaries already projected to EPSG:3112 (required). Contains an edge
        accuracy field (default 'EdgeAcc_m'). All values must be positive.
    mu, sigma : float
        Parameters of the log-normal distribution used to sample the edge accuracy ratio.
    min_ratio, max_ratio : float
        Hard clipping bounds for accepted sampled ratios (rejection sampling). Ensures
        unrealistic extreme ratios are excluded.
    use_lognormal : bool, default True
        If True, sample ratios from log-normal distribution with rejection. If False,
        a fixed_ratio is used for all features.
    fixed_ratio : float, default 1.0
        Ratio used when use_lognormal is False.
    max_attempts : int, default 10000
        Maximum rejection sampling iterations per feature before raising an error.
    log_interval : int, default 100
        Interval for progress printing during buffering.
    edge_acc_field : str, default 'EdgeAcc_m'
        Column name storing edge accuracy distances (meters).
    buffer_field : str, default 'Buffer_m'
        Column name to store the signed buffer distance applied (meters). Positive = outward,
        negative = inward. Inward buffering can fully remove small polygons; such removals are
        counted but not returned.
    area_field : str, default 'Area_km2'
        Column name for recalculated planar area (square kilometres) after dissolution.

    Returns
    -------
    GeoDataFrame
        Dissolved (global) dithered reef boundaries with updated area field. EdgeAcc_m is the
        maximum of contributing features; Buffer_m is the maximum absolute applied buffer among
        merged members (sign retained from the member that had the max absolute value). Area_km2
        is recomputed in planar CRS.

    Assumptions / Constraints
    -------------------------
    * Input CRS must be EPSG:3112 (asserted).
    * All edge accuracy values are > 0.
    * A global dissolve of touching/overlapping polygons is always performed.
    * Attributes (other than EdgeAcc_m, Buffer_m, Area_km2) are aggregated: single unique value
      retained, else semicolon-delimited list of unique values (stringified).

    Notes
    -----
    "Inward removals" refer to cases where a randomly chosen inward buffer distance fully erodes
    a polygon (e.g., small or narrow features). These features are simply skipped (dropped) from
    the buffered set because they have zero area after buffering.
    """
    assert base_gdf.crs is not None, "Input GeoDataFrame must have a CRS."
    # Accept both explicit EPSG code or string forms; safer to compare EPSG number if available.
    epsg = None
    try:
        epsg = base_gdf.crs.to_epsg()
    except Exception:
        pass
    if epsg is None:
        # Fallback textual check
        assert str(base_gdf.crs).endswith("3112"), "Input CRS must be EPSG:3112."
    else:
        assert epsg == 3112, f"Input CRS must be EPSG:3112, got EPSG:{epsg}."

    # Column + value checks
    assert edge_acc_field in base_gdf.columns, f"Missing required field '{edge_acc_field}'."
    assert (base_gdf[edge_acc_field] > 0).all(), f"All '{edge_acc_field}' values must be > 0."

    original_columns = list(base_gdf.columns)
    # We'll add/overwrite buffer_field & ensure area_field later.

    def sample_ratio_single() -> float:
        if not use_lognormal:
            return fixed_ratio
        for _ in range(max_attempts):
            r = np.random.lognormal(mean=mu, sigma=sigma)
            if min_ratio <= r <= max_ratio:
                return r
        raise RuntimeError("Failed to sample ratio within bounds after many attempts.")

    buffered_records = []
    dropped_inward = 0

    for idx, row in base_gdf.iterrows():
        geom = row.geometry
        edge_acc = float(row[edge_acc_field])
        ratio = sample_ratio_single()
        buf_dist = edge_acc * ratio
        # Random inward / outward sign
        signed_dist = -buf_dist if np.random.rand() < 0.5 else buf_dist
        try:
            new_geom = geom.buffer(signed_dist)
        except Exception as e:
            # Skip problematic geometry
            print(f"[WARN] Buffer failed for feature {idx}: {e}", file=sys.stderr)
            continue
        if (new_geom is None) or new_geom.is_empty:
            # inward erosion removed polygon completely
            if signed_dist < 0:
                dropped_inward += 1
            continue
        rec = {c: row[c] for c in original_columns if c != "geometry"}
        rec[buffer_field] = signed_dist
        rec["geometry"] = new_geom
        buffered_records.append(rec)
        if log_interval and (len(buffered_records) % log_interval == 0):
            print(f"Buffered {len(buffered_records)} features (processed {idx+1}/{len(base_gdf)}) ...")

    if not buffered_records:
        raise ValueError("No buffered features produced (all removed or failed).")

    buffered_gdf = gpd.GeoDataFrame(buffered_records, crs=base_gdf.crs)
    # Ensure singlepart geometries
    buffered_gdf = buffered_gdf.explode(index_parts=False, ignore_index=True)
    print(f"Buffered features kept: {len(buffered_gdf)} (dropped inward removals: {dropped_inward})")

    # --- Global dissolve of touching/overlapping features ---
    union_geom = unary_union(buffered_gdf.geometry.values)
    if union_geom.is_empty:
        raise ValueError("Union of buffered geometries is empty.")

    if isinstance(union_geom, Polygon):
        parts = [union_geom]
    elif isinstance(union_geom, MultiPolygon):
        parts = list(union_geom.geoms)
    else:
        parts = []

    parts_gdf = gpd.GeoDataFrame({"geometry": parts}, crs=buffered_gdf.crs)
    parts_gdf["comp_id"] = range(len(parts_gdf))
    join = gpd.sjoin(buffered_gdf, parts_gdf, predicate="intersects", how="inner")

    attr_cols = [c for c in set(buffered_gdf.columns) if c != "geometry"]
    out_rows = []
    for cid, grp in join.groupby("comp_id"):
        comp_geom = parts_gdf.loc[parts_gdf["comp_id"] == cid, "geometry"].iloc[0]

        def agg_attr(col):
            if col in (edge_acc_field, buffer_field, area_field):
                return None
            vals = grp[col].dropna().unique().tolist()
            if not vals:
                return None
            if len(vals) == 1:
                return vals[0]
            return ";".join(sorted(str(v) for v in vals))

        row = {}
        for c in attr_cols:
            if c == edge_acc_field:
                row[c] = float(grp[edge_acc_field].max())
            elif c == buffer_field:
                # choose buffer distance with largest absolute magnitude; keep sign
                bseries = grp[buffer_field]
                idx_max = bseries.abs().idxmax()
                row[c] = float(bseries.loc[idx_max])
            elif c == area_field:
                row[c] = None
            else:
                row[c] = agg_attr(c)
        row["geometry"] = comp_geom
        out_rows.append(row)

    dissolved = gpd.GeoDataFrame(out_rows, crs=base_gdf.crs)

    # Recalculate area (planar) in km^2
    areas = dissolved.geometry.area / 1e6
    dissolved[area_field] = areas

    return dissolved

def main():
    # Seed (if desired) managed outside the reusable function in Monte Carlo contexts.
    if not os.path.exists(BASE_REEF_SHP):
        print(f"[ERROR] Input shapefile not found: {BASE_REEF_SHP}", file=sys.stderr)
        sys.exit(1)

    print(f"Loading base reefs: {BASE_REEF_SHP}")
    base = gpd.read_file(BASE_REEF_SHP)
    if base.empty:
        print("[ERROR] Base reef layer is empty.", file=sys.stderr)
        sys.exit(1)

    # Ensure planar CRS (project if necessary then assert) for this script's workflow.
    if str(base.crs) != TARGET_CRS:
        base = base.to_crs(TARGET_CRS)
    # Function will assert EPSG:3112.

    dissolved = generate_dithered_boundaries(
        base_gdf=base,
        mu=MU,
        sigma=SIGMA,
        min_ratio=MIN_RATIO,
        max_ratio=MAX_RATIO,
        use_lognormal=DITHER_EDGE_ACC_RATIO,
        fixed_ratio=FIXED_EDGE_ACC_RATIO,
        max_attempts=10000,
        log_interval=LOG_INTERVAL,
    )

    # Output writing (already in planar CRS; if original CRS needed, adapt here).
    out_dir = os.path.dirname(OUTPUT_SHP)
    os.makedirs(out_dir, exist_ok=True)
    if os.path.exists(OUTPUT_SHP):
        try:
            os.remove(OUTPUT_SHP)
        except Exception:
            pass
    print(f"Writing output: {OUTPUT_SHP}")
    dissolved.to_file(OUTPUT_SHP)

    # Basic ratios summary from dissolved layer (note: post-dissolve aggregation may differ
    # slightly from per-feature pre-dissolve distribution used in comparative analyses).
    if "EdgeAcc_m" in dissolved.columns and "Buffer_m" in dissolved.columns:
        valid = dissolved[dissolved["EdgeAcc_m"] > 0]
        if not valid.empty:
            ratios = (valid["Buffer_m"].abs() / valid["EdgeAcc_m"]).to_numpy()
            print(
                f"Dissolved ratio stats (n={len(ratios)}): "
                f"mean={np.mean(ratios):.3f} median={np.median(ratios):.3f} "
                f"min={np.min(ratios):.3f} max={np.max(ratios):.3f}"
            )
    print("Done.")

if __name__ == "__main__":
    main()
