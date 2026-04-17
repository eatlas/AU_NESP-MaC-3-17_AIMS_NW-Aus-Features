"""Script: A03-version-changes.py

Compares two versions of the NW Australian reef boundary dataset to quantify
changes: new features added, features deleted, boundary improvements, and
attribute updates. Outputs a descriptive console report and a verification
shapefile.

Two input modes:
  Default      : Compares raw edit shapefiles.
  --processed  : Compares processed output shapefiles.

See A03-version-changes-spec.md for full specification.
"""

import argparse
import configparser
import os
import sys

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely import make_valid

# ── Configuration ──────────────────────────────────────────────────────────────
cfg = configparser.ConfigParser()
cfg.read("config.ini")
version = cfg.get("general", "version")
previous_version = cfg.get("general", "previous_version")

# ── Constants ──────────────────────────────────────────────────────────────────
IOU_THRESHOLD = 0.50
GEOM_TOLERANCE = 1e-9
METRIC_CRS = "EPSG:3112"
STORAGE_CRS = "EPSG:4283"
COMPARE_ATTRS = [
    'EdgeSrc', 'FeatConf', 'TypeConf', 'EdgeAcc_m',
    'DepthCat', 'DepthCatSr', 'RB_Type_L3', 'Attachment'
]

# ── CLI ────────────────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser(
    description="Compare two versions of the reef boundary dataset."
)
parser.add_argument(
    "--processed", action="store_true",
    help="Compare processed output shapefiles instead of raw edit files."
)
args = parser.parse_args()

# ── Paths ──────────────────────────────────────────────────────────────────────
if args.processed:
    old_path = cfg.get("paths", "previous_processed")
    new_path = cfg.get("paths", "current_processed")
    input_desc = "Processed output shapefiles"
else:
    old_path = cfg.get("paths", "previous_edit")
    new_path = cfg.get("paths", "current_edit")
    input_desc = "Raw edit shapefiles"

OUT_DIR = f"working/{version}/A03"
OUT_SHP = os.path.join(OUT_DIR, f"Version-changes_{version}.shp")

# ── Step 1: Load datasets ─────────────────────────────────────────────────────
missing = []
if not os.path.exists(old_path):
    missing.append(old_path)
if not os.path.exists(new_path):
    missing.append(new_path)
if missing:
    for p in missing:
        print(f"ERROR: File not found: {p}")
    sys.exit(1)

print(f"Loading previous version: {old_path}")
old_gdf = gpd.read_file(old_path)
print(f"Loading current version:  {new_path}")
new_gdf = gpd.read_file(new_path)

# Fix geometries and drop nulls/empties
old_gdf["geometry"] = old_gdf.geometry.apply(
    lambda g: make_valid(g) if g is not None else None
)
new_gdf["geometry"] = new_gdf.geometry.apply(
    lambda g: make_valid(g) if g is not None else None
)
old_gdf = old_gdf[~old_gdf.geometry.isna() & ~old_gdf.geometry.is_empty].copy()
new_gdf = new_gdf[~new_gdf.geometry.isna() & ~new_gdf.geometry.is_empty].copy()

n_old = len(old_gdf)
n_new = len(new_gdf)
print(f"Previous version features: {n_old}")
print(f"Current version features:  {n_new}")

# Assign stable integer indices for tracking
old_gdf = old_gdf.reset_index(drop=True)
new_gdf = new_gdf.reset_index(drop=True)
old_gdf["_old_idx"] = old_gdf.index
new_gdf["_new_idx"] = new_gdf.index


# ── Helper: check if two attribute sets differ ─────────────────────────────────
def attrs_changed(old_row, new_row):
    """Return True if any COMPARE_ATTRS value differs between matched rows."""
    for attr in COMPARE_ATTRS:
        old_val = old_row.get(attr)
        new_val = new_row.get(attr)
        # Treat NaN/None as equal
        old_na = old_val is None or (isinstance(old_val, float) and np.isnan(old_val))
        new_na = new_val is None or (isinstance(new_val, float) and np.isnan(new_val))
        if old_na and new_na:
            continue
        if old_na != new_na:
            return True
        if old_val != new_val:
            return True
    return False


# ── Step 2: Phase 1 — Exact geometry matching ─────────────────────────────────
print("\nPhase 1: Exact geometry matching ...")

# Spatial join to find candidate pairs
candidates = gpd.sjoin(
    new_gdf[["_new_idx", "geometry"]],
    old_gdf[["_old_idx", "geometry"]],
    how="inner",
    predicate="intersects"
)

# Test exact match on candidates
exact_pairs = []  # list of (new_idx, old_idx)
matched_new = set()
matched_old = set()

for _, row in candidates.iterrows():
    ni = row["_new_idx"]
    oi = row["_old_idx"]
    if ni in matched_new or oi in matched_old:
        continue
    new_geom = new_gdf.loc[ni, "geometry"]
    old_geom = old_gdf.loc[oi, "geometry"]
    if new_geom.equals_exact(old_geom, GEOM_TOLERANCE):
        exact_pairs.append((ni, oi))
        matched_new.add(ni)
        matched_old.add(oi)

print(f"  Exact matches found: {len(exact_pairs)}")

# Pools of remaining unmatched features
remaining_new_idx = set(new_gdf.index) - matched_new
remaining_old_idx = set(old_gdf.index) - matched_old

# ── Step 3: Phase 2 — Substantial geometry matching ───────────────────────────
print("Phase 2: Substantial geometry matching (IoU) ...")

substantial_pairs = []  # list of (new_idx, old_idx, iou)

if remaining_new_idx and remaining_old_idx:
    rem_new = new_gdf.loc[list(remaining_new_idx)].copy()
    rem_old = old_gdf.loc[list(remaining_old_idx)].copy()

    # Spatial join on remaining pools
    cands2 = gpd.sjoin(
        rem_new[["_new_idx", "geometry"]],
        rem_old[["_old_idx", "geometry"]],
        how="inner",
        predicate="intersects"
    )

    if len(cands2) > 0:
        # Reproject to metric CRS for area calculations
        rem_new_m = rem_new.to_crs(METRIC_CRS)
        rem_old_m = rem_old.to_crs(METRIC_CRS)

        iou_records = []
        for _, row in cands2.iterrows():
            ni = row["_new_idx"]
            oi = row["_old_idx"]
            new_geom_m = rem_new_m.loc[ni, "geometry"]
            old_geom_m = rem_old_m.loc[oi, "geometry"]
            try:
                intersection = new_geom_m.intersection(old_geom_m)
                union = new_geom_m.union(old_geom_m)
                if union.area > 0:
                    iou = intersection.area / union.area
                else:
                    iou = 0.0
            except Exception:
                iou = 0.0
            if iou >= IOU_THRESHOLD:
                iou_records.append((ni, oi, iou))

        # Greedy 1:1 assignment, highest IoU first
        iou_records.sort(key=lambda x: x[2], reverse=True)
        assigned_new = set()
        assigned_old = set()
        for ni, oi, iou in iou_records:
            if ni not in assigned_new and oi not in assigned_old:
                substantial_pairs.append((ni, oi, iou))
                assigned_new.add(ni)
                assigned_old.add(oi)

print(f"  Substantial matches found: {len(substantial_pairs)}")

# Update pools
for ni, oi, _ in substantial_pairs:
    matched_new.add(ni)
    matched_old.add(oi)

remaining_new_idx = set(new_gdf.index) - matched_new
remaining_old_idx = set(old_gdf.index) - matched_old

# ── Step 4: Phase 3 — Classify remaining by overlap ───────────────────────────
print("Phase 3: Overlap-based classification ...")

overlap_improved_new = set()   # new features that overlap old (improved)
overlap_rearranged_old = set() # old features that overlap new (not deleted)

if remaining_new_idx and remaining_old_idx:
    rem_new3 = new_gdf.loc[list(remaining_new_idx)].copy()
    rem_old3 = old_gdf.loc[list(remaining_old_idx)].copy()

    # Find any overlapping pairs
    cands3 = gpd.sjoin(
        rem_new3[["_new_idx", "geometry"]],
        rem_old3[["_old_idx", "geometry"]],
        how="inner",
        predicate="intersects"
    )
    if len(cands3) > 0:
        overlap_improved_new = set(cands3["_new_idx"].unique())
        overlap_rearranged_old = set(cands3["_old_idx"].unique())

true_new_idx = remaining_new_idx - overlap_improved_new
true_deleted_idx = remaining_old_idx - overlap_rearranged_old

n_overlap_improved = len(overlap_improved_new)
n_new_features = len(true_new_idx)
n_deleted = len(true_deleted_idx)
print(f"  Overlap-only improved (new side): {n_overlap_improved}")
print(f"  Rearranged old features (not deleted): {len(overlap_rearranged_old)}")
print(f"  Truly new features: {n_new_features}")
print(f"  Deleted features: {n_deleted}")

# ── Step 5: Attribute comparison ───────────────────────────────────────────────
print("\nComparing attributes on matched features ...")

# Build attribute-change flags for exact matches
exact_attr_flags = {}
for ni, oi in exact_pairs:
    exact_attr_flags[ni] = attrs_changed(old_gdf.loc[oi], new_gdf.loc[ni])

# Build attribute-change flags for substantial matches
subst_attr_flags = {}
for ni, oi, _ in substantial_pairs:
    subst_attr_flags[ni] = attrs_changed(old_gdf.loc[oi], new_gdf.loc[ni])

n_unchanged = len(exact_pairs)
n_iou_improved = len(substantial_pairs)
n_improved = n_iou_improved + n_overlap_improved
n_attr_compared = n_unchanged + n_iou_improved
n_attr_changed = sum(exact_attr_flags.values()) + sum(subst_attr_flags.values())

print(f"  Features with attribute changes: {n_attr_changed} / {n_attr_compared}")

# ── Step 6: Build verification shapefile ───────────────────────────────────────
print(f"\nSaving verification shapefile ...")

records = []

# Exact matches → unchanged
for ni, oi in exact_pairs:
    records.append({
        "geometry": new_gdf.loc[ni, "geometry"],
        "change": "unchanged",
        "attr_chg": exact_attr_flags[ni]
    })

# Substantial matches → improved
for ni, oi, _ in substantial_pairs:
    records.append({
        "geometry": new_gdf.loc[ni, "geometry"],
        "change": "improved",
        "attr_chg": subst_attr_flags[ni]
    })

# Overlap-only improved (new-side features that overlap old but weren't IoU-matched)
for ni in overlap_improved_new:
    records.append({
        "geometry": new_gdf.loc[ni, "geometry"],
        "change": "improved",
        "attr_chg": None
    })

# Truly new features (no overlap with any old feature)
for ni in true_new_idx:
    records.append({
        "geometry": new_gdf.loc[ni, "geometry"],
        "change": "new",
        "attr_chg": None
    })

# Deleted features (old features with no overlap with any new feature)
for oi in true_deleted_idx:
    records.append({
        "geometry": old_gdf.loc[oi, "geometry"],
        "change": "deleted",
        "attr_chg": None
    })

out_gdf = gpd.GeoDataFrame(records, crs=STORAGE_CRS)
os.makedirs(OUT_DIR, exist_ok=True)
out_gdf.to_file(OUT_SHP)
print(f"  Saved to: {OUT_SHP}")

# ── Step 7: Console report ────────────────────────────────────────────────────
attr_list = ", ".join(COMPARE_ATTRS)

report = f"""
=============================================================
Version Change Report: {previous_version} \u2192 {version}
=============================================================
Input: {input_desc}
  Previous: {old_path}
  Current:  {new_path}
Previous version features: {n_old}
Current version features:  {n_new}

--- Feature Matching ---
Features with identical geometry found in both versions
(indicating no change to the feature boundary):
  Unchanged features: {n_unchanged}

Features where the geometry overlaps between versions but is not
identical (indicating an improvement to the boundary):
  Improved features: {n_improved}
    IoU-matched (>= {IOU_THRESHOLD}): {n_iou_improved}
    Overlap-only:                     {n_overlap_improved}

Features present in the current version with no spatial overlap
with any feature in the previous version (indicating a newly
digitised feature):
  New features: {n_new_features}

Features present in the previous version with no spatial overlap
with any feature in the current version (indicating a removed
feature):
  Deleted features: {n_deleted}

--- Attribute Changes ---
Among features with a 1:1 match (unchanged + IoU-matched improved),
the number where one or more attributes ({attr_list}) were updated:
  Features with attribute changes: {n_attr_changed} / {n_attr_compared}

Verification shapefile saved to: {OUT_SHP}
============================================================="""

print(report)
