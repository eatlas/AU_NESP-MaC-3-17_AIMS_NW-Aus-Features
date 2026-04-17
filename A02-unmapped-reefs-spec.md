# A02-unmapped-reefs.py — Processing Specification

## Overview

This script determines which reef features in the North and West Australian Tropical Reef Features dataset were previously mapped by existing spatial datasets, and which are newly mapped. It implements the methodology described in `A02-unmapped-reefs-appendix.md` using a combination of automated spatial matching (Tier 1) and manual tagging against bathymetry and marine charts (Tier 2).

The script operates in two modes:

- **`--prepare`**: Creates empty template point shapefiles for manual tagging in QGIS.
- **Default (no flag)**: Runs the full analysis — builds countable reef clusters, automated spatial matching, incorporation of manual tags, classification of each reef cluster, annotated output, and summary report.


## Configuration

All paths derive from `config.ini`:

```ini
[general]
in_3p_path = data/v1-0/in-3p
version = v1-0
```


## Inputs

| Dataset | Path | Notes |
|---|---|---|
| L2 dissolved reef features | `working/{version}/12/NW-Features_{version}_RB-Type-L2.shp` | Output of script 12. Contains `RB_Type_L2` field with values including "Coral Reef" and "Rocky Reef". |
| AHS seabed area features | `{in_3p_path}/AU_NESP-D3_AHS_Reefs/sbdare_a.shp` | Pre-filtered by `NATIVE_CL` to reef-like features (see below). |
| ReefKIM | `data/{version}/in-3p-mirror/WA_CU_WAMSI-2-1-3-1_ReefKIM/Reef_KIM.shp` | Kimberley region reef geodatabase. |
| UNEP Global Coral Reefs | `{in_3p_path}/World_WCMC_CoralReefs2021_v4_1/01_Data/WCMC008_CoralReef2021_Py_v4_1.shp` | Global dataset; must be clipped before use. |
| GA Geotopo 250k Marine Hazards | `{in_3p_path}/GA_GeoTopo250k_S3/Vector_data/Hydrography/marinehazardareas.shp` | Shallow reefs around Australia |
| AHO uncharted areas | `data/{version}/in/AHO-Uncharted/AHO-Uncharted-areas_2025.shp` | Optional, for supplementary uncharted-areas subset analysis (not implemented in initial version). |
| Bathymetry manual tags (mapped) | `data/{version}/in/prior-mapped-reefs/bathy-mapped.shp` | Point shapefile. Created manually in QGIS. |
| Bathymetry manual tags (indicated) | `data/{version}/in/prior-mapped-reefs/bathy-indicated.shp` | Point shapefile. Created manually in QGIS. |
| Chart manual tags (mapped) | `data/{version}/in/prior-mapped-reefs/chart-mapped.shp` | Point shapefile. Created manually in QGIS. |
| Chart manual tags (indicated) | `data/{version}/in/prior-mapped-reefs/chart-indicated.shp` | Point shapefile. Created manually in QGIS. |
| Study boundary | `data/{version}/extras/study-boundary/NW-Aus-Features-study-boundary.shp` | Study area polygon used to clip missed-reefs output. |


## Outputs

| File | Path | Description |
|---|---|---|
| Countable reef clusters | `working/{version}/A02/countable-reef-clusters.shp` | Clustered L2 reef polygons meeting the ≥ 100 m effective width threshold. Used for manual tagging in QGIS. CRS: EPSG:4283. |
| Annotated reef clusters | `working/{version}/A02/unmapped-reefs-analysis.shp` | Final output with all source-match and classification attributes. CRS: EPSG:4283. |
| Potential missed reefs | `working/{version}/A02/potential-missed-reefs.shp` | Reference dataset features (Tier 1 polygons and Tier 2 buffered points) that do not overlap any L2 feature and fall within the study boundary. Each row carries a `source` attribute identifying which dataset it came from. CRS: EPSG:4283. |
| Template point shapefiles | `data/{version}/in/prior-mapped-reefs/*.shp` (× 4) | Empty point shapefiles created by `--prepare`. Not overwritten if they already exist. CRS: EPSG:4283. |
| Invalid L2 features (geographic) | `working/{version}/A02/invalid-geom-L2-input.shp` | L2 features that are topologically invalid in EPSG:4283 after `make_valid`. Created only when invalid features are found. CRS: EPSG:4283. |
| Invalid L2 features (metric) | `working/{version}/A02/invalid-geom-L2-metric.shp` | L2 features that become topologically invalid after reprojection to EPSG:3112. Created only when invalid features are found. CRS: EPSG:3112. |


## Coordinate Reference Systems

| Purpose | CRS |
|---|---|
| Storage / output | EPSG:4283 (GDA94 geographic) |
| Buffering, area calculation, clustering | EPSG:3112 (GDA94 / Geoscience Australia Lambert) |


## Processing Pipeline

### Phase 1: Prepare template files (`--prepare`)

#### Step 1.1 — Create empty template point shapefiles

Create the following four empty point shapefiles in `data/{version}/in/prior-mapped-reefs/` with CRS EPSG:4283:

1. `bathy-mapped.shp`
2. `bathy-indicated.shp`
3. `chart-mapped.shp`
4. `chart-indicated.shp`

Schema: geometry column only (Point type). No additional attribute columns are needed since the file name determines the tag meaning.

**Guard**: Do not overwrite any existing shapefile. If a file already exists, skip it and print a message.

#### Step 1.2 — Print prepare summary

Print:
- The path to each template file, noting whether it was created or skipped.
- A description of the recommended workflow:
  1. Run the script in default (analysis) mode. This produces the countable reef clusters shapefile at `working/{version}/A02/countable-reef-clusters.shp`.
  2. Open that file in QGIS alongside marine charts and bathymetry to review clusters not matched by automated reference datasets.
  3. For clusters recorded in bathymetry or marine charts, place a point in the appropriate template shapefile.
  4. Re-run the script in default mode to incorporate the manual tags into the final classification.


### Phase 2: Full analysis (default mode)

#### Step 2.1 — Build countable reef clusters

Run the following pipeline to build countable reef clusters from the L2 input.

##### Step 2.1a — Load and filter L2 features

1. Read `working/{version}/12/NW-Features_{version}_RB-Type-L2.shp`.
2. Filter to features where `RB_Type_L2` ∈ {"Coral Reef", "Rocky Reef"}.
3. Fix geometries with `shapely.make_valid()`. Drop null/empty geometries.
4. Validate the resulting geometries (still in EPSG:4283). If any features remain invalid after `make_valid`, print a warning, attach the GEOS invalidity reason as an `inv_reason` attribute, and save the problem features to `working/{version}/A02/invalid-geom-L2-input.shp`.

##### Step 2.1b — Cluster by proximity

The clustering follows the methodology of Lawrey, Bycroft & Hammerton (2026).

1. Reproject to **EPSG:3112** for metric operations.
2. Validate the reprojected geometries. Reprojection can introduce new topology invalidity in features that were valid in geographic CRS. If any invalid features are found:
   a. Print a warning and save the problem features (with `inv_reason` attribute) to `working/{version}/A02/invalid-geom-L2-metric.shp`.
   b. Attempt repair with `make_valid`. Drop null/empty results.
   c. If any features remain invalid after repair, print a count and exclude them from further processing.
3. For each reef type ("Coral Reef", "Rocky Reef") separately:
   a. Buffer each polygon by **50 m** (half the 100 m clustering distance).
   b. Compute the unary union of all buffered polygons.
   c. Explode the union into singlepart polygons. Each singlepart polygon defines a cluster envelope.
   d. Assign a unique `cluster_id` to each envelope.
4. Spatially join the **original unbuffered** L2 polygons back to the cluster envelopes (predicate: `intersects`) to determine cluster membership.
5. For each cluster, compute:
   - `cluster_area_m2`: sum of original unbuffered polygon areas (in EPSG:3112).
   - `eff_width_m`: effective reef width = $2\sqrt{A/\pi}$ where $A$ = `cluster_area_m2`.
6. Dissolve the original unbuffered polygons within each cluster into a single multipolygon per cluster (unary union of originals, not the buffered envelopes).

##### Step 2.1c — Filter to countable reefs

1. Retain only clusters with `eff_width_m` ≥ 100 m (corresponding to area ≥ ~7,854 m²).
2. Assign a size class to each cluster:

| Size class | Effective width |
|---|---|
| Small | 100–300 m |
| Medium | 300–1,000 m |
| Large | 1,000–3,000 m |
| Very large | > 3,000 m |

##### Step 2.1d — Build cluster attributes

Each countable reef cluster carries the following attributes:

| Field | Type | Description |
|---|---|---|
| `cluster_id` | int | Unique identifier. |
| `RB_Type_L2` | str | "Coral Reef" or "Rocky Reef". |
| `n_parts` | int | Number of original L2 polygons in the cluster. |
| `c_area_km2` | float | Sum of original polygon areas (km², EPSG:3112). |
| `eff_wid_m` | float | Effective reef width (m). Rounded to 1 decimal. |
| `size_class` | str | Size class label (Small / Medium / Large / Very large). |

##### Step 2.1e — Save countable reef clusters

1. Reproject cluster geometries back to **EPSG:4283**.
2. Save to `working/{version}/A02/countable-reef-clusters.shp`.

If `countable-reef-clusters.shp` already exists from a prior run, regenerate it to ensure consistency with the current L2 input.

#### Step 2.2 — Load and preprocess reference datasets

**AHS seabed area features:**
1. Read `{in_3p_path}/AU_NESP-D3_AHS_Reefs/sbdare_a.shp`.
2. Pre-filter to reef-like features: `NATIVE_CL` ∈ {"coral", "sand/mud/coral", "rock", "stone"}.
3. Fix geometries with `make_valid`. Drop null/empty geometries. Reproject to EPSG:4283.

**ReefKIM:**
1. Read `data/{version}/in-3p-mirror/WA_CU_WAMSI-2-1-3-1_ReefKIM/Reef_KIM.shp`.
2. Fix geometries with `make_valid`. Drop null/empty geometries. Reproject to EPSG:4283.

**UNEP Global Coral Reefs:**
1. Read `{in_3p_path}/World_WCMC_CoralReefs2021_v4_1/01_Data/WCMC008_CoralReef2021_Py_v4_1.shp`.
2. Clip to bounding box: longitude 95°–168.5°, latitude −34° to −9°. Use `geopandas.clip()` with a bounding box polygon, or `cx` indexer, **before** further processing to reduce memory usage.
3. Fix geometries with `make_valid`. Drop null/empty geometries. Reproject to EPSG:4283.

**GA Geotopo 250k Marine Hazards:**
1. Read `{in_3p_path}/GA_GeoTopo250k_S3/Vector_data/Hydrography/marinehazardareas.shp`.
2. Fix geometries with `make_valid`. Drop null/empty geometries. Reproject to EPSG:4283.

#### Step 2.3 — Automated spatial matching (Tier 1)

For each countable reef cluster, test for spatial intersection (`intersects` predicate) against each reference dataset. Any degree of overlap is sufficient.

| Source flag field | Matched against | Notes |
|---|---|---|
| `src_AHS` | AHS reef features | All filtered AHS features (coral + rock + stone + sand/mud/coral) are matched against all reef clusters regardless of reef type. This ensures that the match isn't dependent on classification |
| `src_KIM` | ReefKIM features | All ReefKIM features matched against all reef clusters. |
| `src_UNEP` | UNEP coral reef polygons | All clipped UNEP features matched against all reef clusters. |
| `src_GA` | GA Geotopo 250k marine hazard areas | All features matched against all reef clusters. |

Implementation: use `gpd.sjoin()` with `predicate="intersects"`, then collect unique cluster IDs that appear in the join result.

#### Step 2.4 — Incorporate manual tags (Tier 2)

Load each of the four manual tagging point shapefiles (if they exist and contain features):

| Source flag field | Point shapefile |
|---|---|
| `src_bath_m` | `data/{version}/in/prior-mapped-reefs/bathy-mapped.shp` |
| `src_bath_i` | `data/{version}/in/prior-mapped-reefs/bathy-indicated.shp` |
| `src_cht_m` | `data/{version}/in/prior-mapped-reefs/chart-mapped.shp` |
| `src_cht_i` | `data/{version}/in/prior-mapped-reefs/chart-indicated.shp` |

For each point shapefile:
1. Reproject points to **EPSG:3112** (metric CRS).
2. Buffer each point to a **50 m radius** (100 m diameter) polygon to allow for spatial uncertainty in manual tagging.
3. Reproject the buffered polygons back to **EPSG:4283**.
4. Spatially join the buffered polygons to countable reef cluster polygons using the `intersects` predicate (i.e., a match occurs if the buffered polygon overlaps any part of a cluster).
5. Collect unique cluster IDs that intersect at least one buffered polygon.
6. Set the corresponding source flag to `True` for those clusters.

If a point shapefile does not exist or is empty, the corresponding source flag remains `False` for all clusters.

#### Step 2.5 — Classification

For each countable reef cluster, assign:

**`known_stat`** (str) — Three-tier classification:

| Value | Criteria |
|---|---|
| `Previously mapped` | Any of `src_AHS`, `src_KIM`, `src_UNEP`, `src_GA`, `src_bathy_m`, or `src_chart_m` is True. |
| `Previously indicated` | None of the "mapped" sources is True, but `src_bathy_i` or `src_chart_i` is True. |
| `Newly mapped` | None of the above. |

**`prev_map`** (bool) — `True` if `known_state == "Previously mapped"`, else `False`. This is the convenience boolean for QGIS styling.

#### Step 2.6 — Save annotated reef clusters

The output shapefile `working/{version}/A02/unmapped-reefs-analysis.shp` contains one row per countable reef cluster with all attributes from Step 1.4 plus:

| Field | Type | Description |
|---|---|---|
| `src_AHS` | bool | Matched AHS reef feature. |
| `src_KIM` | bool | Matched ReefKIM feature. |
| `src_UNEP` | bool | Matched UNEP coral reef polygon. |
| `src_GA` | bool | Matched GA Geotopo 250k marine hazard area. |
| `src_bath_m` | bool | Tagged as mapped in bathymetry (manual). |
| `src_bath_i` | bool | Tagged as indicated in bathymetry (manual). |
| `src_cht_m` | bool | Tagged as mapped on marine chart (manual). |
| `src_cht_i` | bool | Tagged as indicated on marine chart (manual). |
| `known_stat` | str | "Previously mapped" / "Previously indicated" / "Newly mapped". |
| `prev_map` | bool | True if previously mapped. |

CRS: EPSG:4283.

#### Step 2.7 — Print summary report

Print a structured summary:

```
========================================
 Unmapped Reefs Analysis — {version}
========================================

Countable reef clusters (effective width >= 100 m, separated by > 100 m):
  Coral Reef:  {n}
  Rocky Reef:  {n}
  Total:       {n}

Tier 1 automated matches:
  AHS:     {n} clusters
  ReefKIM: {n} clusters
  UNEP:    {n} clusters
  GA:      {n} clusters

Tier 2 manual tags:
  Bathymetry mapped:    {n} clusters
  Bathymetry indicated: {n} clusters
  Chart mapped:         {n} clusters
  Chart indicated:      {n} clusters

Classification summary — Coral Reef:
  Previously mapped:    {n}
  Previously indicated: {n}
  Newly mapped:         {n}

Classification summary — Rocky Reef:
  Previously mapped:    {n}
  Previously indicated: {n}
  Newly mapped:         {n}

Classification summary — All reefs:
  Previously mapped:    {n}
  Previously indicated: {n}
  Newly mapped:         {n}

Size class breakdown of all countable reefs:
  Coral Reef:
    Small (100–300 m):       {n}
    Medium (300–1,000 m):    {n}
    Large (1,000–3,000 m):   {n}
    Very large (> 3,000 m):  {n}
  Rocky Reef:
    Small (100–300 m):       {n}
    Medium (300–1,000 m):    {n}
    Large (1,000–3,000 m):   {n}
    Very large (> 3,000 m):  {n}

Size class breakdown of newly mapped reefs:
  Coral Reef:
    Small (100–300 m):       {n}  ({p}%)
    Medium (300–1,000 m):    {n}  ({p}%)
    Large (1,000–3,000 m):   {n}  ({p}%)
    Very large (> 3,000 m):  {n}  ({p}%)
  Rocky Reef:
    Small (100–300 m):       {n}  ({p}%)
    Medium (300–1,000 m):    {n}  ({p}%)
    Large (1,000–3,000 m):   {n}  ({p}%)
    Very large (> 3,000 m):  {n}  ({p}%)

Output: working/{version}/A02/unmapped-reefs-analysis.shp

Potential missed reefs (reference features not overlapping L2):
    AHS              {n}
    GA               {n}
    ReefKIM          {n}
    UNEP             {n}
    Bathy mapped     {n}
    Bathy indicated  {n}
    Chart mapped     {n}
    Chart indicated  {n}
    Total            {n}

  Output: working/{version}/A02/potential-missed-reefs.shp
```

#### Step 2.8 — Missed-reefs analysis

Identify reference dataset features that do not overlap any mapped L2 feature. These are potential reefs that exist in reference datasets but were not captured in the reef mapping.

1. Load the full L2 dissolved reef features dataset (`working/{version}/12/NW-Features_{version}_RB-Type-L2.shp`) **without filtering by reef type**. All L2 types (coral reef, rocky reef, sand banks, etc.) are included as the mask. Fix geometries and reproject to EPSG:4283.
2. Compile all reference datasets into a single GeoDataFrame with a `source` attribute:
   - Tier 1 polygon datasets: AHS (pre-filtered to reef-like `NATIVE_CL`), ReefKIM, UNEP (bbox-clipped), GA — reuse the already-loaded and preprocessed versions from Step 2.2.
   - Tier 2 manual tag point shapefiles: buffer each point by `BATHY_CHART_POINT_BUFFER_M` (250 m) in EPSG:3112 and reproject the resulting polygons back to EPSG:4283. Process all four files: bathy-mapped, bathy-indicated, chart-mapped, chart-indicated.
3. For each feature in the combined reference dataset, test for spatial intersection with any L2 feature using `gpd.sjoin()` with a left join and `predicate="intersects"`. Features with no match (NaN in `index_right`) are retained as potential missed reefs.
4. Clip the non-overlapping features to the study boundary (`data/{version}/extras/study-boundary/NW-Aus-Features-study-boundary.shp`). Drop null/empty geometries after clipping.
5. Save the result to `working/{version}/A02/potential-missed-reefs.shp`.
6. Print a summary table showing the count of potential missed-reef features per source dataset and the total.


## CLI Interface

```
usage: A02-unmapped-reefs.py [--prepare]

Assessment of previously unmapped reefs.

optional arguments:
  --prepare   Create empty template point shapefiles for manual tagging,
              then exit. Does not run any spatial analysis.
```

When `--prepare` is given, only the template shapefiles are created. When omitted, the full analysis runs, including building countable reef clusters, spatial matching, classification, and summary reporting.


## Key Design Decisions

1. **Clustering before matching**: Reef polygons are clustered into countable reefs before comparison with reference datasets. This means the manual tagging is done at the scale of countable reef clusters, and the reported counts refer to countable reefs, not raw L2 polygons.

2. **No type distinction for automated matching**: All three reference datasets (AHS, ReefKIM, UNEP) are matched against both coral reef and rocky reef clusters. The AHS pre-filter removes non-reef substrate types (sand, mud, gravel, unknown) but retains both coral-type and rock-type features in a single comparison set. This avoids false negatives from classification mismatches between datasets.

3. **Conservative intersection threshold**: Any spatial overlap between a cluster and a reference polygon classifies the cluster as matched. No minimum overlap area is required. This is deliberately conservative — it reduces the count of newly mapped reefs to produce a more defensible result.

4. **No-overwrite guard on manual tagging files**: The `--prepare` step never overwrites existing point shapefiles. This prevents accidental loss of completed manual tagging work.

5. **UNEP bounding box clip**: The global UNEP dataset is clipped to 95°–168.5° E, 34°–9° S before spatial operations. This is necessary for memory and performance.

6. **Geometry validation and repair**: All polygon datasets are repaired using `shapely.make_valid()` rather than the simpler `buffer(0)` approach. `make_valid()` handles a wider range of topology errors (self-intersections, ring orientation, degenerate rings) and is the recommended approach in Shapely 2.x. The L2 input is validated twice: once in geographic CRS (EPSG:4283) after initial loading, and once after reprojection to metric CRS (EPSG:3112), because reprojection itself can introduce new topology invalidity. Any remaining invalid features are saved to diagnostic shapefiles with a GEOS-provided invalidity reason (`inv_reason` attribute) to support debugging in QGIS.

7. **Reef counting methodology reference**: The clustering distance (100 m), effective width formula, minimum size threshold (100 m), and size classes follow Lawrey, Bycroft & Hammerton (2026).


## Dependencies

- `geopandas`
- `pandas`
- `numpy`
- `shapely`
- Standard library: `os`, `argparse`, `configparser`, `math`


---

# A02b-tier1-overlap-analysis.py — Processing Specification

## Overview

This script analyses the contribution of each reference dataset (Tier 1 automated and Tier 2 manual) to the classification of countable reef clusters. It reads the annotated reef clusters output from `A02-unmapped-reefs.py` and reports individual coverage, cumulative contribution, and marginal drop for all eight source datasets.

The script has no modes or flags. It reads the existing analysis shapefile and prints a structured report to the console.


## Inputs

| Dataset | Path | Notes |
|---|---|---|
| Annotated reef clusters | `working/{version}/A02/unmapped-reefs-analysis.shp` | Output of `A02-unmapped-reefs.py`. Must contain boolean source flag columns `src_AHS`, `src_KIM`, `src_UNEP`, `src_GA`, `src_bath_m`, `src_bath_i`, `src_cht_m`, `src_cht_i`. |


## Outputs

Console output only. No files are written.


## Configuration

All paths derive from `config.ini`:

```ini
[general]
version = v1-0
```


## Processing Pipeline

### Step 1 — Load annotated clusters

1. Read `working/{version}/A02/unmapped-reefs-analysis.shp`.
2. Cast all eight source flag columns to boolean.
3. Compute summary flags:
   - `any_t1`: True if any Tier 1 source flag is True.
   - `any_mapped`: True if any Tier 1 or Tier 2 mapped source is True.
   - `any_all`: True if any of the eight source flags is True.

### Step 2 — Individual dataset coverage

For each of the eight source flag columns, count the number of clusters where the flag is True. Report the count and the percentage of total countable reef clusters. Group the output by tier: Tier 1 (automated), Tier 2 mapped, Tier 2 indicated.

### Step 3 — Cumulative contribution

Add datasets one at a time and track the cumulative number of matched clusters. The order is:
1. Tier 1 sources sorted by decreasing individual coverage.
2. Tier 2 mapped sources sorted by decreasing individual coverage.
3. Tier 2 indicated sources sorted by decreasing individual coverage.

For each addition, report the new cumulative total, the number of new clusters added, and the cumulative percentage.

### Step 4 — Marginal drop analysis

For each of the eight datasets, compute how many clusters would lose **all** matches if that dataset were removed while retaining the other seven. The marginal drop treats mapped and indicated sources uniformly — it measures whether removing a dataset causes any cluster to become completely unmatched by any source. Report in the same order as the cumulative contribution.


## Print format

```
============================================================
 Dataset Contribution Analysis — {version}
============================================================

Total countable reef clusters: {n}
Matched by at least one Tier 1 source:      {n}
Matched by at least one mapped source:       {n}
Matched by at least one source (all):        {n}
Not matched by any source:                   {n}

--- Individual dataset coverage ---
  Tier 1 (automated):
    AHS              {n}  ({p}%)
    ReefKIM          {n}  ({p}%)
    UNEP             {n}  ({p}%)
    GA               {n}  ({p}%)
  Tier 2 (manual — mapped):
    Bathy mapped     {n}  ({p}%)
    Chart mapped     {n}  ({p}%)
  Tier 2 (manual — indicated):
    Bathy indicated  {n}  ({p}%)
    Chart indicated  {n}  ({p}%)

--- Cumulative contribution (adding datasets by coverage) ---
  + {dataset} → {n} matched (+{n} new, {p}% cumulative)
  ...

--- Marginal drop (clusters lost if this dataset were removed) ---
  Remove {dataset} → lose {n} clusters ({p}%)
  ...
```


## CLI Interface

```
usage: A02b-tier1-overlap-analysis.py
```

No arguments. Reads configuration from `config.ini`.


## Dependencies

- `geopandas`
- `pandas`
- Standard library: `configparser`, `os`
