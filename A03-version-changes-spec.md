# A03-version-changes — Processing Specification

## Overview

Compares two versions of the NW Australian reef boundary dataset to quantify changes:
new features added, features deleted, boundary improvements, and attribute updates.
Outputs a descriptive console report and a verification shapefile.

## Configuration

Reads from `config.ini`:

```ini
[general]
version = v1-0
previous_version = v0-4

[paths]
previous_edit = data/v0-4/in/Reef-Boundaries_v0-4_edit.shp
current_edit = data/v1-0/in/Reef-Boundaries_v1-0_edit.shp
previous_processed = data/v0-4/out/AU_NESP-MaC-3-17_AIMS_NW-Aus-Features_v0-4.shp
current_processed = data/v1-0/out/full-classes/AU_NESP-MaC-3-17_AIMS_NW-Aus-Features_L3_v1-0.shp
```

## CLI Interface

```
python A03-version-changes.py [--processed]
```

- **Default**: Compares raw edit shapefiles (`paths.previous_edit`, `paths.current_edit`).
- **`--processed`**: Compares processed output shapefiles (`paths.previous_processed`,
  `paths.current_processed`). Exits with an error message if either file is missing.

## Inputs

All input paths are read from the `[paths]` section of `config.ini`.

| Dataset | Config key |
|---|---|
| Previous edit | `previous_edit` |
| Current edit | `current_edit` |
| Previous processed | `previous_processed` |
| Current processed | `current_processed` |

## Outputs

| File | Path | Description |
|---|---|---|
| Verification shapefile | `working/{version}/A03/Version-changes_{version}.shp` | All features with a `change` attribute. CRS: EPSG:4283. |

The `change` attribute values: `unchanged`, `improved`, `new`, `deleted`.

- `deleted` features use the geometry from the previous version.
- All other features use the geometry from the current version.

## Constants

```python
IOU_THRESHOLD = 0.50        # Minimum IoU for a substantial geometry match
GEOM_TOLERANCE = 1e-9       # Tolerance for exact geometry comparison (degrees)
METRIC_CRS = "EPSG:3112"    # For area calculations (IoU)
STORAGE_CRS = "EPSG:4283"   # For output
COMPARE_ATTRS = [
    'EdgeSrc', 'FeatConf', 'TypeConf', 'EdgeAcc_m',
    'DepthCat', 'DepthCatSr', 'RB_Type_L3', 'Attachment'
]
```

## Processing Pipeline

### Step 1 — Load datasets

1. Read `config.ini` to get `version` and `previous_version`.
2. Based on `--processed` flag, select appropriate file paths for old and new datasets.
3. Verify both files exist. If either is missing, print the missing path and exit.
4. Read both shapefiles into GeoDataFrames. Fix geometries with `make_valid()`.
   Drop null/empty geometries.

### Step 2 — Phase 1: Exact geometry matching

Find features with identical geometry between old and new versions.

1. Use `gpd.sjoin(new_gdf, old_gdf, predicate="intersects")` to find candidate
   pairs. This leverages the spatial index to avoid O(n²) comparisons.
2. For each candidate pair, test `new_geom.equals_exact(old_geom, GEOM_TOLERANCE)`.
3. Where an exact match is found, link the pair (1:1). If a feature has multiple exact
   matches, take the first and leave others in the unmatched pool.
4. Remove matched features from both the old and new pools.

### Step 3 — Phase 2: Substantial geometry matching (improved boundaries)

Match remaining features that have significantly overlapping geometry.

1. Use `gpd.sjoin()` on the remaining unmatched old and new features to find
   intersecting candidate pairs.
2. For each candidate pair, compute IoU in METRIC_CRS:
   $\text{IoU} = \frac{\text{Area}(A \cap B)}{\text{Area}(A \cup B)}$
3. Collect all pairs with IoU ≥ `IOU_THRESHOLD`.
4. Sort pairs by IoU descending. Greedily assign 1:1 matches: for each pair (highest
   IoU first), if neither the old nor new feature has already been assigned, link them.
5. Remove matched features from both pools.

### Step 4 — Phase 3: Classify remaining features by overlap

Use spatial overlap on the remaining unmatched pools to distinguish rearranged
features from truly new or deleted ones.

1. Use `gpd.sjoin()` on the remaining unmatched old and new features to identify
   overlapping pairs.
2. Old features that overlap **any** remaining new feature → discard from the
   deleted pool (they were rearranged, not removed).
3. Old features with **no** overlap with any new feature → `deleted`.
4. New features that overlap **any** remaining old feature → `improved`
   (`attr_chg` = `None`, since there is no clean 1:1 pair for comparison).
5. New features with **no** overlap with any old feature → `new`.

### Step 5 — Attribute comparison

For features with a 1:1 pair (from Phase 1 exact matches and Phase 2 IoU matches
only; not overlap-only improved features from Phase 3):

1. Compare the values of each attribute in `COMPARE_ATTRS` between the old and
   new feature. Treat `None`/`NaN` values as equal to each other.
2. Mark a feature as having attribute changes if **any** attribute differs.

### Step 6 — Build verification shapefile

1. Create output directory `working/{version}/A03/`.
2. Build a GeoDataFrame with columns: `geometry`, `change`, `attr_chg`.
   - **unchanged** and **improved**: geometry from the new version.
   - **new**: geometry from the new version.
   - **deleted**: geometry from the old version.
   - For exact matches → `change` = `unchanged`.
   - For substantial matches → `change` = `improved`.
   - `attr_chg`: `True` if any attribute in `COMPARE_ATTRS` differs between
     matched old/new features, `False` if none differ. Set to `None` (null)
     for `new`, `deleted`, and overlap-only `improved` features (Phase 3).
3. Set CRS to EPSG:4283. Save to `working/{version}/A03/Version-changes_{version}.shp`.

### Step 7 — Console report

Print a structured report. Each section includes a brief description followed by the
count. Use this format:

```
=============================================================
Version Change Report: {previous_version} → {version}
=============================================================
Input: {input_file_description}
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

Verification shapefile saved to: {output_path}
=============================================================
```