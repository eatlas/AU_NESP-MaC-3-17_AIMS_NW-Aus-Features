"""
Script: 12-make-RB_Type_L2.py

Purpose
- Produce a North/West Australia-only version of the dataset dissolved at RB_Type_L2 so that
  coral and rocky reefs are represented by their full outer extents rather than their finer,
  part-based RB_Type_L3 components. This enables counting reefs at the L2 precision.

Classification context
- The reef mapping uses a hierarchical classification:
  * RB_Type_L3 (most detailed): coral and rocky reefs are subdivided into distinct parts and types.
    For example, "Coral Reef" (actively growing reef) and "Coral Reef Flat" (sandy flat) are both
    parts of the same larger reef structure.
  * RB_Type_L2 (coarser): these L3 parts roll up into broader classes, e.g. both examples above are
    classified as "Coral Reef" at L2.
- This script dissolves features by RB_Type_L2 to create polygons representing the full outer extent
  of each reef/rocky reef at L2, rather than separate L3 parts.

Processing overview
1) Input: AU_NESP-MaC-3-17_AIMS_NW-Aus-Features_L3_{version}.shp (NW-only dataset produced by step 11).
2) Validation:
   - Assert RB_Type_L2 is present and non-empty for all features.
   - Fail if Attachment, DepthCat, FeatConf, or TypeConf contain unexpected enum values.
3) Geometry clean: fix topology using buffer(0).
4) Sliver repair: after dissolving each L2 group, apply buffer(+SLIVER_EPS).buffer(-SLIVER_EPS)
   to close infinitely-thin holes and boundary cracks caused by floating-point precision errors
   along the seams of adjacent features. SLIVER_EPS = 1e-6 degrees (~0.1 m at these latitudes).
5) Dissolve by RB_Type_L2:
   - Build the unary union for each L2 class and explode into singlepart components so that each
     dissolved reef is a separate polygon.
   - For each singlepart component, aggregate attributes from the original L3 features that
     intersect that component (per-component aggregation):
       • RB_L3_Agg: unique RB_Type_L3 values joined by semicolons.
       • Attachment: priority-based choice Land > Fringing > Oceanic > Isolated; also record the
         set of attachments (AttSet) for QA.
       • DepthCat: choose the highest category using the order Land > Surface > Intertidal >
         Very Shallow > Shallow > Deep.
       • DepthCatSr and EdgeSrc: unique sources joined by semicolons.
       • FeatConf and TypeConf: take the lowest confidence across members (Very Low < Low < Medium < High).
       • EdgeAcc_m: take the maximum (worst) accuracy in metres.
   - Flag components where multiple Attachment values were merged (AttSet contains ';').
6) Area: compute Area_km2 in EPSG:3112, round to 4 decimal places; keep output CRS unchanged (EPSG:4283).
7) Outputs:
   - Main dissolved singlepart features: AU_NESP-MaC-3-17_AIMS_NW-Aus-Features_L2_{version}.shp
     Fields include RB_Type_L2, RB_L3_Agg, Attachment, DepthCat, DepthCatSr, FeatConf, TypeConf,
     EdgeSrc, EdgeAcc_m, Area_km2, geometry.
   - QA features with mixed Attachment values: working/{version}/12/multi-attachment-values.shp
     Contains the same attributes plus AttSet to aid debugging.

Failure modes
- Assertion error if any RB_Type_L2 is null/empty.
- Assertion error if enumerated fields contain unexpected values.
"""

import configparser
import os
import geopandas as gpd
import pandas as pd
import numpy as np
from shapely.ops import unary_union
cfg = configparser.ConfigParser()
cfg.read("config.ini")
in_3p_path = cfg.get("general", "in_3p_path")
version = cfg.get("general", "version")
    
INPUT_SHP = cfg.get("paths", "current_processed")
OUTPUT_SHP = cfg.get("paths", "current_processed_L2")
MULTI_ATTACHMENT_SHP = f"working/{version}/12/multi-attachment-values.shp"

# Attachment priority rule (Land > Fringing > Oceanic > otherwise Isolated)
ATT_PRIORITY = ["Land", "Fringing", "Oceanic"]
ATT_ALL = ["Land", "Isolated", "Fringing", "Oceanic"]  # enumeration for ordered listing

# Depth category order (highest to lowest)
DEPTH_ORDER = ["Land", "Surface", "Intertidal", "Very Shallow", "Shallow", "Deep"]
DEPTH_RANK = {v: i for i, v in enumerate(DEPTH_ORDER)}  # lower index = higher

# Confidence order (worst to best ranking via numeric score)
CONF_SCORE = {"Very Low": 0, "Low": 1, "Medium": 2, "High": 3}

# Small buffer (degrees) used to close floating-point slivers/gaps after dissolve.
# Applied as buffer(+eps).buffer(-eps): the outward pass seals sub-pixel holes along
# internal seams; the inward pass restores the outer boundary to its original extent.
SLIVER_EPS = 1e-6

def unique_nonempty(values):
    vals = [str(v).strip() for v in values if pd.notna(v) and str(v).strip() != ""]
    # deterministic ordering
    return sorted(set(vals))

def join_semicolon(values):
    vals = unique_nonempty(values)
    return ";".join(vals) if vals else ""

def choose_attachment(values):
    vals = unique_nonempty(values)
    s = set(vals)
    if "Land" in s:
        return "Land", vals
    if "Fringing" in s:
        return "Fringing", vals
    if "Oceanic" in s:
        return "Oceanic", vals
    # if we have other values (e.g., Isolated only), default to Isolated if present, else empty
    if "Isolated" in s:
        return "Isolated", vals
    return (vals[0] if vals else ""), vals

def choose_depthcat(values):
    # pick the highest: smallest index in DEPTH_ORDER
    vals = unique_nonempty(values)
    # fallback: if none are in the known list, return first value
    if not vals:
        return ""
    ranked = [(DEPTH_RANK.get(v, 999), v) for v in vals]
    ranked.sort(key=lambda t: t[0])
    return ranked[0][1]

def choose_worst_conf(values):
    vals = unique_nonempty(values)
    if not vals:
        return ""
    # unknown values get worst score -1 to be conservative
    worst = None
    worst_score = 999
    for v in vals:
        score = CONF_SCORE.get(v, -1)
        if score < worst_score:
            worst = v
            worst_score = score
    return worst

def max_edge_acc(values):
    # numeric max of EdgeAcc_m
    nums = pd.to_numeric(pd.Series(values), errors="coerce")
    if nums.notna().any():
        return int(nums.max())
    return 0

def assert_enums(gdf: gpd.GeoDataFrame):
    # Fail if unexpected enum values are present
    def vals(col):
        return sorted({str(v).strip() for v in gdf[col].fillna("").astype(str)})

    att_unknown = [v for v in vals("Attachment") if v and v not in ATT_ALL]
    depth_unknown = [v for v in vals("DepthCat") if v and v not in DEPTH_ORDER]
    conf_allowed = set(CONF_SCORE.keys())
    feat_conf_unknown = [v for v in vals("FeatConf") if v and v not in conf_allowed]
    type_conf_unknown = [v for v in vals("TypeConf") if v and v not in conf_allowed]

    errs = []
    if att_unknown:
        errs.append(f"Attachment has unexpected values: {att_unknown}")
    if depth_unknown:
        errs.append(f"DepthCat has unexpected values: {depth_unknown}")
    if feat_conf_unknown:
        errs.append(f"FeatConf has unexpected values: {feat_conf_unknown}")
    if type_conf_unknown:
        errs.append(f"TypeConf has unexpected values: {type_conf_unknown}")

    if errs:
        raise AssertionError(" | ".join(errs))

def dissolve_by_l2(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    # Dissolve by RB_Type_L2, then aggregate attributes per singlepart component
    out_parts = []
    for l2, grp in gdf.groupby("RB_Type_L2"):
        union_geom = unary_union(grp.geometry)
        # Close floating-point slivers and boundary cracks produced by the dissolve.
        union_geom = union_geom.buffer(SLIVER_EPS).buffer(-SLIVER_EPS)
        parts_gdf = gpd.GeoDataFrame(geometry=[union_geom], crs=gdf.crs).explode(index_parts=False).reset_index(drop=True)
        parts_gdf["part_id"] = range(len(parts_gdf))

        # Spatially join original features to each dissolved part to aggregate only merged members
        join = gpd.sjoin(grp, parts_gdf[["geometry", "part_id"]], predicate="intersects", how="inner")

        for pid, jgrp in join.groupby("index_right"):
            part_geom = parts_gdf.loc[pid, "geometry"]
            # Aggregate attributes from original members of this component
            rb_l3_agg = join_semicolon(jgrp["RB_Type_L3"])
            att_choice, att_set = choose_attachment(jgrp["Attachment"])
            depthcat = choose_depthcat(jgrp["DepthCat"])
            depthcat_sr = join_semicolon(jgrp["DepthCatSr"])
            feats_conf = choose_worst_conf(jgrp["FeatConf"])
            type_conf = choose_worst_conf(jgrp["TypeConf"])
            edge_src = join_semicolon(jgrp["EdgeSrc"])
            edge_acc = max_edge_acc(jgrp["EdgeAcc_m"])

            att_set_ordered = [a for a in ATT_ALL if a in set(unique_nonempty(jgrp["Attachment"]))]
            att_set_join = ";".join(att_set_ordered)

            out_parts.append({
                "RB_Type_L2": l2,
                "RB_L3_Agg": rb_l3_agg,
                "Attachment": att_choice,
                "AttSet": att_set_join,  # QA
                "DepthCat": depthcat,
                "DepthCatSr": depthcat_sr,
                "FeatConf": feats_conf,
                "TypeConf": type_conf,
                "EdgeSrc": edge_src,
                "EdgeAcc_m": int(edge_acc),
                "geometry": part_geom
            })

    return gpd.GeoDataFrame(out_parts, crs=gdf.crs)

def main():
    print("Reading input shapefile...")
    gdf = gpd.read_file(INPUT_SHP)
    print(f"  Loaded {len(gdf)} features.")

    # Assert RB_Type_L2 present and non-null/non-empty
    assert "RB_Type_L2" in gdf.columns, "RB_Type_L2 field missing."
    non_empty_mask = gdf["RB_Type_L2"].notna() & (gdf["RB_Type_L2"].astype(str).str.strip() != "")
    assert non_empty_mask.all(), "Found null/empty RB_Type_L2 values."

    # Strict enum validation
    assert_enums(gdf)

    # Clean geometry
    print("Cleaning geometry...")
    gdf["geometry"] = gdf.geometry.buffer(0)
    gdf = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty]

    # Dissolve by RB_Type_L2 with per-component aggregation
    print("Dissolving by RB_Type_L2 (per-component aggregation)...")
    singleparts = dissolve_by_l2(gdf)

    # Flag multi-attachment merged features (for QA output)
    singleparts["HasMultiAtt"] = singleparts["AttSet"].str.contains(";")

    # Compute area in EPSG:3112, keep geometry CRS unchanged
    print("Computing area (EPSG:3112)...")
    sp_proj = singleparts.to_crs(epsg=3112)
    singleparts["Area_km2"] = (sp_proj.geometry.area / 1e6).round(4)

    # Output dir
    os.makedirs(os.path.dirname(OUTPUT_SHP), exist_ok=True)

    # Save main output (exclude QA fields)
    cols = ["RB_Type_L2", "RB_L3_Agg", "Attachment", "DepthCat", "DepthCatSr",
            "FeatConf", "TypeConf", "EdgeSrc", "EdgeAcc_m", "Area_km2", "geometry"]
    print(f"Saving dissolved output to {OUTPUT_SHP}...")
    singleparts[cols].to_file(OUTPUT_SHP)

    # Save multi-attachment features after merge (singlepart polygons)
    multi = singleparts[singleparts["HasMultiAtt"]].copy()
    if not multi.empty:
        os.makedirs(os.path.dirname(MULTI_ATTACHMENT_SHP), exist_ok=True)
        qa_cols = ["RB_Type_L2", "RB_L3_Agg", "Attachment", "AttSet", "DepthCat", "DepthCatSr",
                   "FeatConf", "TypeConf", "EdgeSrc", "EdgeAcc_m", "Area_km2", "geometry"]
        print(f"Saving multi-attachment QA output to {MULTI_ATTACHMENT_SHP}...")
        multi[qa_cols].to_file(MULTI_ATTACHMENT_SHP)
    else:
        print("No multi-attachment merged features detected; QA file not written.")

    print("Done.")

if __name__ == "__main__":
    main()
