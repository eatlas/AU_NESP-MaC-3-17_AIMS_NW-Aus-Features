"""Script: A02-unmapped-reefs.py

Assessment of previously unmapped reefs in the North and West Australian Tropical
Reef Features dataset. Determines which reef features were previously mapped by
existing spatial datasets, and which are newly mapped.

Two modes:
  --prepare : Builds countable reef clusters from the L2 dissolved reef dataset and
              creates empty template shapefiles for manual tagging in QGIS.
  Default   : Runs the full analysis — automated spatial matching (Tier 1),
              incorporation of manual tags (Tier 2), classification, annotated
              output, and summary report.

Methodology follows Lawrey, Bycroft & Hammerton (2026).
"""

import argparse
import configparser
import math
import os

import geopandas as gpd
import pandas as pd
from shapely.ops import unary_union
from shapely import make_valid

# ── Configuration ──────────────────────────────────────────────────────────────
cfg = configparser.ConfigParser()
cfg.read("config.ini")
in_3p_path = cfg.get("general", "in_3p_path")
in_3p_path = 'data/v1-0/in-3p'
version = cfg.get("general", "version")
#version = 'v0-4'
# ── Paths ──────────────────────────────────────────────────────────────────────
L2_INPUT = f"working/{version}/12/NW-Features_{version}_RB-Type-L2.shp"
AHS_INPUT = f"{in_3p_path}/AU_NESP-D3_AHS_Reefs/sbdare_a.shp"
REEFKIM_INPUT = f"data/{version}/in-3p-mirror/WA_CU_WAMSI-2-1-3-1_ReefKIM/Reef_KIM.shp"
UNEP_INPUT = (
    f"{in_3p_path}/World_WCMC_CoralReefs2021_v4_1/01_Data/"
    "WCMC008_CoralReef2021_Py_v4_1.shp"
)
GA_INPUT = (
    f"{in_3p_path}/GA_GeoTopo250k_S3/Vector_data/Hydrography/marinehazardareas.shp"
)
MANUAL_TAG_DIR = f"data/{version}/in/prior-mapped-reefs"
BATHY_MAPPED = os.path.join(MANUAL_TAG_DIR, "bathy-mapped.shp")
BATHY_INDICATED = os.path.join(MANUAL_TAG_DIR, "bathy-indicated.shp")
CHART_MAPPED = os.path.join(MANUAL_TAG_DIR, "chart-mapped.shp")
CHART_INDICATED = os.path.join(MANUAL_TAG_DIR, "chart-indicated.shp")

OUT_DIR = f"working/{version}/A02"
CLUSTERS_SHP = os.path.join(OUT_DIR, "countable-reef-clusters.shp")
ANALYSIS_SHP = os.path.join(OUT_DIR, "unmapped-reefs-analysis.shp")

CRS_STORAGE = "EPSG:4283"
CRS_METRIC = "EPSG:3112"

# Effective width bounds (m) for each size class  [low, high)
_SIZE_CLASSES = [
    (100, 300, "Small"),
    (300, 1_000, "Medium"),
    (1_000, 3_000, "Large"),
    (3_000, float("inf"), "Very large"),
]


def _classify_size(eff_width_m):
    for low, high, label in _SIZE_CLASSES:
        if low <= eff_width_m < high:
            return label
    return "Very large"


def deprecated_fix_geom(gdf):
    """Fix geometries with buffer(0) and drop null/empty results."""
    gdf = gdf.copy()
    gdf["geometry"] = gdf["geometry"].buffer(0)
    mask = gdf["geometry"].notna() & ~gdf["geometry"].is_empty
    return gdf[mask].copy()

def _fix_geom(gdf):
    gdf = gdf.copy()
    gdf["geometry"] = gdf["geometry"].apply(lambda g: make_valid(g) if g is not None else None)
    gdf["geometry"] = gdf["geometry"].buffer(0)
    mask = gdf["geometry"].notna() & ~gdf["geometry"].is_empty & gdf.is_valid
    return gdf[mask].copy()


def _explode_union(union_geom):
    """Return a list of singlepart Polygon geometries from a union result."""
    if union_geom is None or union_geom.is_empty:
        return []
    if union_geom.geom_type == "Polygon":
        return [union_geom]
    return [g for g in union_geom.geoms if g.geom_type == "Polygon" and not g.is_empty]


# ─────────────────────────────────────────────────────────────────────────────
# Phase 1 — Build countable reef clusters (Steps 1.1–1.5)
# ─────────────────────────────────────────────────────────────────────────────

def build_countable_clusters():
    """Load L2 reef features, cluster by proximity, filter to eff_width >= 100 m.

    Returns a GeoDataFrame in EPSG:4283 with one row per countable reef cluster.
    """
    # Step 1.1 — Load and filter
    print(f"  Loading L2 features from: {L2_INPUT}")
    l2 = gpd.read_file(L2_INPUT)
    l2 = l2[l2["RB_Type_L2"].isin(["Coral Reef", "Rocky Reef"])].copy()
    l2 = _fix_geom(l2)
    l2 = l2.reset_index(drop=True)
    print(f"  {len(l2)} reef polygons after filtering (Coral Reef + Rocky Reef).")

    # Step 1.2 — Cluster by proximity, per reef type
    l2_metric = _fix_geom(l2.to_crs(CRS_METRIC).reset_index(drop=True))
    l2_metric["_area_m2"] = l2_metric.geometry.area

    all_rows = []
    cluster_counter = 0

    for reef_type in ["Coral Reef", "Rocky Reef"]:
        subset = l2_metric[l2_metric["RB_Type_L2"] == reef_type].copy()
        if subset.empty:
            continue

        # Buffer each polygon by 50 m, dissolve, explode to singlepart envelopes
        buffered_union = unary_union(subset.geometry.buffer(50))
        envelope_geoms = _explode_union(buffered_union)

        envelopes = gpd.GeoDataFrame(
            {"cluster_id": range(cluster_counter, cluster_counter + len(envelope_geoms))},
            geometry=envelope_geoms,
            crs=CRS_METRIC,
        ).reset_index(drop=True)
        cluster_counter += len(envelope_geoms)

        # Spatial join: original unbuffered polygons → envelope they fall in
        orig = subset[["_area_m2", "geometry"]].copy()
        joined = gpd.sjoin(
            orig,
            envelopes[["cluster_id", "geometry"]],
            how="left",
            predicate="intersects",
        )

        # Aggregate per cluster: area sum, effective width, dissolved geometry
        for cid, grp in joined.groupby("cluster_id"):
            cluster_area_m2 = grp["_area_m2"].sum()
            eff_width = 2 * math.sqrt(cluster_area_m2 / math.pi)
            # Dissolve original (unbuffered) polygons in this cluster
            dissolved_geom = unary_union(grp.geometry)
            all_rows.append(
                {
                    "cluster_id": int(cid),
                    "RB_Type_L2": reef_type,
                    "n_parts": len(grp),
                    "c_area_km2": round(cluster_area_m2 / 1e6, 4),
                    "eff_wid_m": round(eff_width, 1),
                    "size_class": _classify_size(eff_width),
                    "geometry": dissolved_geom,
                }
            )

    clusters = gpd.GeoDataFrame(all_rows, crs=CRS_METRIC)

    # Step 1.3 — Filter to countable reefs (effective width >= 100 m)
    clusters = clusters[clusters["eff_wid_m"] >= 100].copy().reset_index(drop=True)

    # Step 1.5 — Reproject to storage CRS
    clusters = clusters.to_crs(CRS_STORAGE)
    clusters = clusters[
        ["cluster_id", "RB_Type_L2", "n_parts", "c_area_km2", "eff_wid_m", "size_class", "geometry"]
    ]
    return clusters


# ─────────────────────────────────────────────────────────────────────────────
# Phase 1 — Prepare mode
# ─────────────────────────────────────────────────────────────────────────────

def run_prepare():
    """Create empty template point shapefiles for manual tagging."""
    print("=== Prepare mode ===\n")
    os.makedirs(MANUAL_TAG_DIR, exist_ok=True)

    # Create empty template point shapefiles (no-overwrite guard)
    template_paths = [BATHY_MAPPED, BATHY_INDICATED, CHART_MAPPED, CHART_INDICATED]
    print("Creating template point shapefiles ...")
    created, skipped = [], []
    for path in template_paths:
        if os.path.exists(path):
            print(f"  Skipping (already exists): {path}")
            skipped.append(path)
        else:
            template = gpd.GeoDataFrame(
                geometry=gpd.GeoSeries(dtype="geometry"), crs=CRS_STORAGE
            )
            template.to_file(path, driver="ESRI Shapefile", geometry_type="Point")
            print(f"  Created: {path}")
            created.append(path)

    print("\nNext steps:")
    print(
        "  1. Run this script without --prepare to produce the full analysis.\n"
        "     This generates the countable reef clusters shapefile at:\n"
        f"     {CLUSTERS_SHP}"
    )
    print(
        "  2. Open that file in QGIS alongside marine charts and bathymetry.\n"
        "     Review clusters not matched by the automated reference datasets."
    )
    print(
        "  3. For clusters recorded in bathymetry or marine charts, place a point\n"
        "     in the appropriate template shapefile:"
    )
    for path in template_paths:
        print(f"     {path}")
    print("  4. Re-run this script without --prepare to incorporate the manual tags.")


# ─────────────────────────────────────────────────────────────────────────────
# Phase 2 — Full analysis helpers
# ─────────────────────────────────────────────────────────────────────────────

def _match_clusters(clusters, ref_gdf):
    """Return the set of cluster_ids whose geometry intersects any feature in ref_gdf."""
    joined = gpd.sjoin(
        clusters[["cluster_id", "geometry"]],
        ref_gdf[["geometry"]],
        how="inner",
        predicate="intersects",
    )
    return set(joined["cluster_id"].unique())


def _load_manual_tags(path, clusters):
    """Return the set of cluster_ids that contain at least one point from path."""
    if not os.path.exists(path):
        return set()
    pts = gpd.read_file(path)
    if pts.empty:
        return set()
    pts = pts.to_crs(CRS_STORAGE)
    joined = gpd.sjoin(
        clusters[["cluster_id", "geometry"]],
        pts[["geometry"]],
        how="inner",
        predicate="contains",
    )
    return set(joined["cluster_id"].unique())


# ─────────────────────────────────────────────────────────────────────────────
# Phase 2 — Full analysis
# ─────────────────────────────────────────────────────────────────────────────

def run_analysis():
    """Full analysis: cluster, match, classify, save, report."""
    print("=== Analysis mode ===\n")
    os.makedirs(OUT_DIR, exist_ok=True)

    # Step 2.1 — Build countable reef clusters
    print("Step 1: Building countable reef clusters ...")
    clusters = build_countable_clusters()
    clusters.to_file(CLUSTERS_SHP)
    print(f"  {len(clusters)} countable reef clusters built and saved.")

    # Step 2.2 — Load and preprocess reference datasets
    print("\nStep 2: Loading reference datasets ...")

    print("  Loading AHS seabed area features ...")
    ahs = gpd.read_file(AHS_INPUT)
    ahs = ahs[ahs["NATIVE_CL"].isin(["coral", "sand/mud/coral", "rock", "stone"])].copy()
    ahs = _fix_geom(ahs).to_crs(CRS_STORAGE)
    print(f"    {len(ahs)} features after NATIVE_CL filter.")

    print("  Loading ReefKIM ...")
    reefkim = gpd.read_file(REEFKIM_INPUT)
    reefkim = _fix_geom(reefkim).to_crs(CRS_STORAGE)
    print(f"    {len(reefkim)} features loaded.")

    print("  Loading UNEP Global Coral Reefs (bounding box clip) ...")
    # bbox=(minx, miny, maxx, maxy) — read only features overlapping study region
    unep = gpd.read_file(UNEP_INPUT, bbox=(95, -34, 168.5, -9))
    unep = _fix_geom(unep).to_crs(CRS_STORAGE)
    print(f"    {len(unep)} features after bounding box clip.")

    print("  Loading GA Geotopo 250k Marine Hazards ...")
    ga = gpd.read_file(GA_INPUT)
    ga = _fix_geom(ga).to_crs(CRS_STORAGE)
    print(f"    {len(ga)} features loaded.")

    # Step 2.3 — Tier 1 automated spatial matching
    print("\nStep 3: Tier 1 automated spatial matching ...")
    matched_ahs = _match_clusters(clusters, ahs)
    print(f"  AHS:     {len(matched_ahs)} clusters matched.")
    matched_kim = _match_clusters(clusters, reefkim)
    print(f"  ReefKIM: {len(matched_kim)} clusters matched.")
    matched_unep = _match_clusters(clusters, unep)
    print(f"  UNEP:    {len(matched_unep)} clusters matched.")
    matched_ga = _match_clusters(clusters, ga)
    print(f"  GA:      {len(matched_ga)} clusters matched.")

    # Step 2.4 — Tier 2 manual tags
    print("\nStep 4: Tier 2 manual tags ...")
    tagged_bath_m = _load_manual_tags(BATHY_MAPPED, clusters)
    tagged_bath_i = _load_manual_tags(BATHY_INDICATED, clusters)
    tagged_cht_m = _load_manual_tags(CHART_MAPPED, clusters)
    tagged_cht_i = _load_manual_tags(CHART_INDICATED, clusters)
    print(f"  Bathymetry mapped:    {len(tagged_bath_m)} clusters tagged.")
    print(f"  Bathymetry indicated: {len(tagged_bath_i)} clusters tagged.")
    print(f"  Chart mapped:         {len(tagged_cht_m)} clusters tagged.")
    print(f"  Chart indicated:      {len(tagged_cht_i)} clusters tagged.")

    # Assign source flag columns
    clusters["src_AHS"] = clusters["cluster_id"].isin(matched_ahs)
    clusters["src_KIM"] = clusters["cluster_id"].isin(matched_kim)
    clusters["src_UNEP"] = clusters["cluster_id"].isin(matched_unep)
    clusters["src_GA"] = clusters["cluster_id"].isin(matched_ga)
    clusters["src_bath_m"] = clusters["cluster_id"].isin(tagged_bath_m)
    clusters["src_bath_i"] = clusters["cluster_id"].isin(tagged_bath_i)
    clusters["src_cht_m"] = clusters["cluster_id"].isin(tagged_cht_m)
    clusters["src_cht_i"] = clusters["cluster_id"].isin(tagged_cht_i)

    # Step 2.5 — Classification
    def _classify(row):
        if any(
            [
                row["src_AHS"],
                row["src_KIM"],
                row["src_UNEP"],
                row["src_GA"],
                row["src_bath_m"],
                row["src_cht_m"],
            ]
        ):
            return "Previously mapped"
        if row["src_bath_i"] or row["src_cht_i"]:
            return "Previously indicated"
        return "Newly mapped"

    clusters["known_stat"] = clusters.apply(_classify, axis=1)
    clusters["prev_map"] = clusters["known_stat"] == "Previously mapped"

    # Step 2.6 — Save annotated clusters
    clusters.to_file(ANALYSIS_SHP)
    print(f"\nAnnotated clusters saved to:\n  {ANALYSIS_SHP}")

    # Step 2.7 — Print summary report
    coral = clusters[clusters["RB_Type_L2"] == "Coral Reef"]
    rocky = clusters[clusters["RB_Type_L2"] == "Rocky Reef"]
    newly_mapped = clusters[clusters["known_stat"] == "Newly mapped"]

    print("\n" + "=" * 40)
    print(f" Unmapped Reefs Analysis — {version}")
    print("=" * 40)

    print(
        f"\nCountable reef clusters (effective width >= 100 m, separated by > 100 m):"
    )
    print(f"  Coral Reef:  {len(coral)}")
    print(f"  Rocky Reef:  {len(rocky)}")
    print(f"  Total:       {len(clusters)}")

    print(f"\nTier 1 automated matches:")
    print(f"  AHS:     {len(matched_ahs)} clusters")
    print(f"  ReefKIM: {len(matched_kim)} clusters")
    print(f"  UNEP:    {len(matched_unep)} clusters")
    print(f"  GA:      {len(matched_ga)} clusters")

    print(f"\nTier 2 manual tags:")
    print(f"  Bathymetry mapped:    {len(tagged_bath_m)} clusters")
    print(f"  Bathymetry indicated: {len(tagged_bath_i)} clusters")
    print(f"  Chart mapped:         {len(tagged_cht_m)} clusters")
    print(f"  Chart indicated:      {len(tagged_cht_i)} clusters")

    for label, subset in [
        ("Coral Reef", coral),
        ("Rocky Reef", rocky),
        ("All reefs", clusters),
    ]:
        print(f"\nClassification summary — {label}:")
        for stat in ["Previously mapped", "Previously indicated", "Newly mapped"]:
            n = (subset["known_stat"] == stat).sum()
            print(f"  {stat + ':':<22} {n}")

    print(f"\nSize class breakdown of newly mapped reefs:")
    for reef_type in ["Coral Reef", "Rocky Reef"]:
        print(f"  {reef_type}:")
        s = newly_mapped[newly_mapped["RB_Type_L2"] == reef_type]
        print(f"    Small (100\u2013300 m):       {(s['size_class'] == 'Small').sum()}")
        print(f"    Medium (300\u20131,000 m):    {(s['size_class'] == 'Medium').sum()}")
        print(f"    Large (1,000\u20133,000 m):   {(s['size_class'] == 'Large').sum()}")
        print(f"    Very large (> 3,000 m):  {(s['size_class'] == 'Very large').sum()}")

    print(f"\nOutput: {ANALYSIS_SHP}")


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Assessment of previously unmapped reefs."
    )
    parser.add_argument(
        "--prepare",
        action="store_true",
        help=(
            "Build countable reef clusters and create empty template point shapefiles "
            "for manual tagging, then exit."
        ),
    )
    args = parser.parse_args()

    if args.prepare:
        run_prepare()
    else:
        run_analysis()


if __name__ == "__main__":
    main()
