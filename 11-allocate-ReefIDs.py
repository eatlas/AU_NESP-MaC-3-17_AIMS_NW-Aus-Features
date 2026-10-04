"""
Script: 11-allocate-ReefIDs.py

Purpose:
    Assign permanent, globally unique ReefIDs to reef features after land clipping.
    IDs are allocated at the L2 reef level (the whole geological structure). Where a
    reef consists of multiple L3 components, alphabetic sub-feature suffixes distinguish
    the parts. Where a reef consists of a single L3 component, no suffix is used.
    IDs persist across dataset versions via spatial matching against the previous version.

ReefID Structure:
    R-9140-003a
      |    |  |
      |    |  +- Sub-feature letter (L3 component within the reef)
      |    +---- Feature counter (sequential within grid cell, zero-padded to 3 digits)
      +--------- Grid cell code (4-digit base-10, encodes centroid lon/lat)

Processing Steps:
    1. Load current clipped features, explode multiparts to singleparts.
    2. Determine each feature's RB_Type_L2 class from the crosswalk.
    3. Dissolve touching features of the same L2 class to form L2 groups. Each group = one reef.
    4. Compute centroid of each L2 group (for grid cell assignment).
    5. If --fresh: allocate all ReefIDs from scratch.
    6. Otherwise, load previous L2 and L3 outputs and match spatially:
       a. Project all geometries to the matching CRS (Australian Albers, equal-area, metres).
       b. Score each (current L2 group, previous L2 feature) pair with a sliver test and
          two-sided shares; a candidate relationship requires either share >= 0.1.
       c. Pool candidates per previous reef. Inheritance is exclusive: the
          greatest-absolute-overlap candidate inherits the base ID, the rest receive
          new base IDs with lineage recorded in PrevReefID.
       d. A manual ReefID in the input (from the Edit file) wins over spatial matching.
    7. Assign sub-feature letters (per-base letter pool) and record L3-level lineage
       in PrevReefID for features that receive a new ID.
    8. Verify all allocated ReefIDs are unique; abort on duplicates.
    9. Write the output shapefile (ReefID, PrevReefID, ReefIDNote), the QA shapefile
       for non-inheriting groups, and the allocation log.
       PrevReefID is a semicolon-separated set that accumulates across versions.

See 11-allocate-ReefIDs-spec.md for the full design specification.

Inputs:
    - Current clipped L3 features: working/{version}/10/NW-Aus-Features_{version}.shp
    - Previous version L2 output: config.ini -> previous_processed_L2
    - Previous version L3 output: config.ini -> previous_processed
    - L3-to-L2 crosswalk: data/{version}/in/RB_Type_L3_crosswalk.csv

Outputs:
    - L3 features with ReefID: working/{version}/11/NW-Aus-Features_{version}.shp
    - Poor-match QA shapefile: working/{version}/11/ReefID-poor-matches.shp
    - Allocation log: working/{version}/11/ReefID-allocation-log.csv

Usage:
    python 11-allocate-ReefIDs.py [--fresh]
"""

import argparse
import configparser
import os

import geopandas as gpd
import pandas as pd

from reef_utils import dissolve_to_l2_components, strip_reef_suffix

# ---- Configuration ----
cfg = configparser.ConfigParser()
cfg.read("config.ini")
version = cfg.get("general", "version")

INPUT_SHP = f"working/{version}/10/NW-Aus-Features_{version}.shp"
CROSSWALK_CSV = f"data/{version}/in/RB_Type_L3_crosswalk.csv"
OUTPUT_DIR = f"working/{version}/11"
OUTPUT_SHP = f"{OUTPUT_DIR}/NW-Aus-Features_{version}.shp"
POOR_MATCH_SHP = f"{OUTPUT_DIR}/ReefID-poor-matches.shp"
ALLOCATION_LOG = f"{OUTPUT_DIR}/ReefID-allocation-log.csv"

# Previous version paths
PREVIOUS_L3 = cfg.get("paths", "previous_processed", fallback=None)
PREVIOUS_L2 = cfg.get("paths", "previous_processed_L2", fallback=None)

# Classification version used in crosswalk column names
RB_TYPE_VERSION = "v0-4"

# ---- ReefID encoding constants (base-10, matching Coral Sea convention) ----
PREFIX = "R"
ZERO_PADDING = 3
BASE_CHARS = "0123456789"
ENCODING_BASE = len(BASE_CHARS)
LON_SLICE_SIZE = 360 / ENCODING_BASE
LAT_SLICE_SIZE = 180 / ENCODING_BASE

# ---- Spatial matching parameters ----
# All spatial matching is performed in an equal-area projected CRS (metres) so that
# the sliver test and absolute-area comparisons are meaningful. Australian Albers is
# equal-area everywhere, including the small fraction of the dataset outside its
# nominal area of use. Same CRS and constants as the GBR remap project
# (02a-patch-TS-GBR-Features.py).
MATCH_CRS = 3577             # EPSG:3577 GDA94 / Australian Albers
SLIVER_TOLERANCE_M = 10.0    # intersections eroding away below this are digitising artefacts
SLIVER_WIDTH_FRACTION = 0.25 # erosion cap as a fraction of the smaller feature's inscribed width
CANDIDATE_SHARE = 0.1        # minimum of share_old / share_new for a candidate relationship
LETTER_MATCH_SHARE = 0.5     # minimum share of current feature area to retain a previous letter


def encode_grid(lon, lat):
    """Encode a lon/lat position into a 4-digit grid cell code (base-10)."""
    lon = lon + 180
    lat = lat + 90

    lon_major = int(lon // LON_SLICE_SIZE)
    lat_major = int(lat // LAT_SLICE_SIZE)
    lon_sub = int((lon % LON_SLICE_SIZE) // (LON_SLICE_SIZE / ENCODING_BASE))
    lat_sub = int((lat % LAT_SLICE_SIZE) // (LAT_SLICE_SIZE / ENCODING_BASE))

    return (BASE_CHARS[lon_major] + BASE_CHARS[lon_sub] +
            BASE_CHARS[lat_major] + BASE_CHARS[lat_sub])


def encode_counter(counter):
    """Encode a counter value as a zero-padded base-10 string."""
    encoded = ''
    if counter == 0:
        encoded = BASE_CHARS[0]
    else:
        while counter > 0:
            encoded = BASE_CHARS[counter % ENCODING_BASE] + encoded
            counter //= ENCODING_BASE
    while len(encoded) < ZERO_PADDING:
        encoded = BASE_CHARS[0] + encoded
    return encoded


def decode_counter(encoded_counter):
    """Decode a base-10 encoded counter string to an integer."""
    counter = 0
    for char in encoded_counter:
        counter = counter * ENCODING_BASE + BASE_CHARS.index(char)
    return counter


def strip_suffix(reef_id):
    """Strip trailing letter suffix from a ReefID to get the base form.
    Delegates to shared utility for consistent handling of multi-letter suffixes."""
    return strip_reef_suffix(reef_id)


def inscribed_width(geom, limit):
    """Width of the widest part of a polygon, found by bisection on erosion.

    Returns 2 * limit for anything at least that wide, since the callers only
    care about the narrow end of the range.

    Ported from the GBR remap project (02a-patch-TS-GBR-Features.py).
    """
    if not geom.buffer(-limit).is_empty:
        return 2 * limit
    lo, hi = 0.0, limit
    for _ in range(16):
        mid = (lo + hi) / 2
        if geom.buffer(-mid).is_empty:
            hi = mid
        else:
            lo = mid
    return 2 * lo


def sliver_tolerance(geom_a, geom_b):
    """Erosion distance to use for a pair, reduced for small features.

    A fixed tolerance cannot judge a feature whose whole width is comparable to
    the tolerance itself, because eroding it leaves nothing whatever the overlap
    represents. The tolerance is therefore capped at a fraction of the width of
    the smaller of the two polygons.

    Ported from the GBR remap project (02a-patch-TS-GBR-Features.py).
    """
    smaller = geom_a if geom_a.area <= geom_b.area else geom_b
    limit = SLIVER_TOLERANCE_M / SLIVER_WIDTH_FRACTION / 2
    if not smaller.buffer(-limit).is_empty:
        return SLIVER_TOLERANCE_M
    return min(SLIVER_TOLERANCE_M,
               SLIVER_WIDTH_FRACTION * inscribed_width(smaller, limit))


def score_pair(cur_geom, prev_geom):
    """Score a current/previous polygon pair in an equal-area projection.

    Returns None where the polygons do not intersect, otherwise a dict holding
    the intersection area, the share of each polygon's area that the
    intersection represents (share_old = of the previous polygon, share_new =
    of the current one), and whether the intersection survives erosion.
    Erosion distinguishes a genuine overlap from a long thin contact produced by
    coordinate precision or an eye-judged division. The erosion distance is
    SLIVER_TOLERANCE_M, reduced on small features by sliver_tolerance.

    Ported from the GBR remap project (02a-patch-TS-GBR-Features.py).
    """
    if cur_geom is None or prev_geom is None:
        return None
    try:
        intersection = cur_geom.intersection(prev_geom)
        if intersection.is_empty:
            return None
        area = intersection.area
        if area <= 0:
            return None
        prev_area = prev_geom.area
        cur_area = cur_geom.area
        # A multipart intersection survives if any part survives erosion.
        survives = not intersection.buffer(-SLIVER_TOLERANCE_M).is_empty
        if not survives:
            tolerance = sliver_tolerance(prev_geom, cur_geom)
            if tolerance < SLIVER_TOLERANCE_M:
                survives = not intersection.buffer(-tolerance).is_empty
    except Exception:
        # Invalid geometry (e.g. GEOS topology exception): treat as no
        # scorable relationship rather than failing the run
        return None
    return {
        'area': area,
        'share_old': area / prev_area if prev_area > 0 else 0.0,
        'share_new': area / cur_area if cur_area > 0 else 0.0,
        'survives': survives,
    }


def is_candidate(scored):
    """A scored pair is a candidate relationship if it survives the sliver test
    and either share reaches CANDIDATE_SHARE."""
    if scored is None or not scored['survives']:
        return False
    return max(scored['share_old'], scored['share_new']) >= CANDIDATE_SHARE


def build_l2_groups(gdf, crosswalk):
    """
    Dissolve touching features of the same L2 class to form L2 groups.
    Returns a list of dicts with group info and a mapping from feature index to group_id.

    Uses the shared dissolve_to_l2_components() utility to ensure consistent
    clustering with 13-make-RB_Type_L2.py (same sliver buffer, geometry cleaning,
    and spatial join logic).
    """
    # Map each feature to its L2 class
    l3_to_l2 = dict(zip(
        crosswalk[f'RB_Type_L3_{RB_TYPE_VERSION}'],
        crosswalk['RB_Type_L2']
    ))
    gdf = gdf.copy()
    gdf['RB_Type_L2'] = gdf['RB_Type_L3'].map(l3_to_l2)

    # Check for unmapped L3 classes
    unmapped = gdf[gdf['RB_Type_L2'].isna()]
    if not unmapped.empty:
        missing_classes = unmapped['RB_Type_L3'].unique()
        raise ValueError(
            f"Cannot map {len(unmapped)} features to L2. "
            f"Missing L3 classes in crosswalk: {list(missing_classes)}"
        )

    # Use shared utility for consistent L2 clustering
    components = dissolve_to_l2_components(gdf)

    # Convert to the groups format expected by this script
    groups = []
    feature_to_group = {}
    for group_id, comp in enumerate(components):
        groups.append({
            'group_id': group_id,
            'l2_class': comp['l2_class'],
            'geometry': comp['geometry'],
            'member_indices': comp['member_indices'],
        })
        for idx in comp['member_indices']:
            feature_to_group[idx] = group_id

    return groups, feature_to_group


def allocate_fresh(groups, gdf):
    """
    Allocate all ReefIDs from scratch. Groups are sorted by centroid_sum within each grid cell.
    """
    # Compute centroid for each group
    for grp in groups:
        centroid = grp['geometry'].centroid
        grp['centroid_lon'] = centroid.x
        grp['centroid_lat'] = centroid.y
        grp['grid_cell'] = encode_grid(centroid.x, centroid.y)
        grp['centroid_sum'] = centroid.x + centroid.y

    # Check for manual overrides in the input
    for grp in groups:
        override_id = None
        for idx in grp['member_indices']:
            feat_id = gdf.at[idx, 'ReefID'] if 'ReefID' in gdf.columns else None
            if pd.notna(feat_id) and feat_id != '':
                override_id = strip_suffix(str(feat_id))
                break
        grp['override_id'] = override_id

    # Sort groups by grid cell then centroid_sum for deterministic allocation
    groups_sorted = sorted(groups, key=lambda g: (g['grid_cell'], g['centroid_sum']))

    # Track counters per grid cell
    grid_counters = {}  # grid_cell -> next counter value
    used_ids = set()  # track all allocated base IDs

    # First pass: apply overrides (they consume their grid cell slot)
    for grp in groups_sorted:
        if grp['override_id']:
            used_ids.add(grp['override_id'])
            # Parse the counter from the override to update grid counter
            parts = grp['override_id'].split('-')
            if len(parts) == 3:
                grid_cell = parts[1]
                counter_val = decode_counter(parts[2])
                if grid_cell not in grid_counters:
                    grid_counters[grid_cell] = 0
                grid_counters[grid_cell] = max(
                    grid_counters[grid_cell], counter_val + 1
                )

    # Second pass: allocate new IDs
    for grp in groups_sorted:
        if grp['override_id']:
            grp['base_id'] = grp['override_id']
        else:
            grid_cell = grp['grid_cell']
            if grid_cell not in grid_counters:
                grid_counters[grid_cell] = 0

            counter = grid_counters[grid_cell]
            base_id = f"{PREFIX}-{grid_cell}-{encode_counter(counter)}"
            while base_id in used_ids:
                counter += 1
                base_id = f"{PREFIX}-{grid_cell}-{encode_counter(counter)}"

            grp['base_id'] = base_id
            used_ids.add(base_id)
            grid_counters[grid_cell] = counter + 1

    # Assign sub-feature letters
    assign_letters_fresh(groups_sorted, gdf)

    return groups_sorted


def assign_letters_fresh(groups, gdf):
    """
    Assign sub-feature letters for fresh allocation.
    Single-component groups: no letter.
    Multi-component groups: letters by area descending.
    """
    def generate_suffix(index):
        """Generate suffix (single or multi-letter) for a given index."""
        suffix = ""
        while index >= 0:
            suffix = chr(ord('a') + (index % 26)) + suffix
            index = (index // 26) - 1
        return suffix

    for grp in groups:
        members = grp['member_indices']
        if len(members) == 1:
            # Single component: no letter suffix
            grp['feature_ids'] = {members[0]: grp['base_id']}
        else:
            # Multi-component groups: sort by area descending, assign suffixes
            areas = [(idx, gdf.loc[idx, 'geometry'].area) for idx in members]
            areas.sort(key=lambda x: -x[1])
            grp['feature_ids'] = {}
            for i, (idx, _) in enumerate(areas):
                suffix = generate_suffix(i)
                grp['feature_ids'][idx] = f"{grp['base_id']}{suffix}"


def allocate_matched(groups, gdf, prev_l2_gdf, prev_l3_gdf):
    """
    Allocate ReefIDs by matching against the previous version.

    All spatial matching is performed in the matching CRS (equal-area, metres).
    Current L2 groups form candidate relationships with previous L2 features
    (sliver test + two-sided shares). Candidates pool per previous reef and
    inheritance is exclusive: only the greatest-absolute-overlap candidate
    inherits the base ID; the rest receive new base IDs.

    Returns (groups, poor_matches, inherited_prev, inherited_notes) where
    inherited_prev/inherited_notes map feature index -> set of previous-version
    values inherited from the best-passing previous L3 feature.
    """
    match_crs = f"EPSG:{MATCH_CRS}"
    gdf_m = gdf.to_crs(match_crs)
    prev_l2_m = prev_l2_gdf.to_crs(match_crs)
    prev_l3_m = prev_l3_gdf.to_crs(match_crs)

    # Compute centroids and grid cells for current groups (geographic CRS)
    for grp in groups:
        centroid = grp['geometry'].centroid
        grp['centroid_lon'] = centroid.x
        grp['centroid_lat'] = centroid.y
        grp['grid_cell'] = encode_grid(centroid.x, centroid.y)
        grp['centroid_sum'] = centroid.x + centroid.y

    # Projected group geometries for spatial matching
    grp_geoms_m = gpd.GeoDataFrame(
        geometry=[g['geometry'] for g in groups], crs=gdf.crs
    ).to_crs(match_crs).geometry
    for grp, geom_m in zip(groups, grp_geoms_m):
        grp['geom_match'] = geom_m

    # Build set of all existing IDs in previous version
    prev_base_ids = set()
    if 'ReefID' in prev_l2_m.columns:
        for rid in prev_l2_m['ReefID'].dropna():
            prev_base_ids.add(strip_suffix(str(rid)))
    elif 'ReefID' in prev_l3_m.columns:
        for rid in prev_l3_m['ReefID'].dropna():
            prev_base_ids.add(strip_suffix(str(rid)))

    # Track counters per grid cell from previous version
    grid_counters = {}
    for base_id in prev_base_ids:
        parts = base_id.split('-')
        if len(parts) == 3:
            grid_cell = parts[1]
            counter_val = decode_counter(parts[2])
            if grid_cell not in grid_counters:
                grid_counters[grid_cell] = 0
            grid_counters[grid_cell] = max(
                grid_counters[grid_cell], counter_val + 1
            )

    used_ids = set(prev_base_ids)

    # ---- L2-level candidate scoring ----
    n_pairs = 0
    n_slivers = 0
    prev_l2_sindex = prev_l2_m.sindex
    has_l2_id = 'ReefID' in prev_l2_m.columns

    for grp in groups:
        grp['l2_candidates'] = []
        grp['inherited'] = False

        # Check manual override first (wins over spatial matching)
        override_id = None
        for idx in grp['member_indices']:
            feat_id = gdf.at[idx, 'ReefID'] if 'ReefID' in gdf.columns else None
            if pd.notna(feat_id) and feat_id != '':
                override_id = strip_suffix(str(feat_id))
                break

        if override_id:
            grp['base_id'] = override_id
            grp['match_quality'] = 'override'
            grp['inherited'] = True
            used_ids.add(override_id)
            # Update grid counter
            parts = override_id.split('-')
            if len(parts) == 3:
                grid_cell = parts[1]
                counter_val = decode_counter(parts[2])
                if grid_cell not in grid_counters:
                    grid_counters[grid_cell] = 0
                grid_counters[grid_cell] = max(
                    grid_counters[grid_cell], counter_val + 1
                )
            continue

        grp_geom_m = grp['geom_match']
        for pos in prev_l2_sindex.intersection(grp_geom_m.bounds):
            if has_l2_id:
                prev_id = prev_l2_m.iloc[pos]['ReefID']
                if pd.isna(prev_id) or str(prev_id) == '':
                    continue  # nothing to inherit from this previous feature
            else:
                continue
            scored = score_pair(grp_geom_m, prev_l2_m.geometry.iloc[pos])
            if scored is None:
                continue
            n_pairs += 1
            if not scored['survives']:
                n_slivers += 1
                continue
            if is_candidate(scored):
                grp['l2_candidates'].append((pos, scored))

    print(f"  Scored {n_pairs} group/previous-L2 pairs "
          f"({n_slivers} rejected as digitising slivers)")

    # ---- Pool candidates per previous reef; exclusive inheritance ----
    pools = {}  # prev index -> list of (group, overlap area)
    for grp in groups:
        for cidx, scored in grp['l2_candidates']:
            pools.setdefault(cidx, []).append((grp, scored['area']))

    for grp in groups:
        grp['won_pools'] = []
    for cidx, members in pools.items():
        if len(members) == 1:
            winner, area = members[0]
        else:
            winner, area = max(members, key=lambda m: m[1])
        winner['won_pools'].append((cidx, area))

    n_split_pools = sum(1 for m in pools.values() if len(m) > 1)
    print(f"  Formed {len(pools)} candidate pools "
          f"({n_split_pools} with multiple candidates)")

    # ---- Assign base IDs ----
    poor_matches = []
    for grp in groups:
        if 'base_id' in grp:
            # Manual override already handled
            continue

        if grp['won_pools']:
            # Good match: inherit previous ID (exclusive pool winner)
            cidx, _ = max(grp['won_pools'], key=lambda t: t[1])
            base = strip_suffix(str(prev_l2_m.iloc[cidx]['ReefID']))
            grp['base_id'] = base
            grp['inherited'] = True
            grp['match_quality'] = 'matched'
            best = next(s for c, s in grp['l2_candidates'] if c == cidx)
            grp['match_quality'] = (
                f"matched (share_new {best['share_new']:.1%}, "
                f"share_old {best['share_old']:.1%})"
            )
            used_ids.add(base)
        else:
            # No winning pool: allocate new ID
            grid_cell = grp['grid_cell']
            if grid_cell not in grid_counters:
                grid_counters[grid_cell] = 0

            counter = grid_counters[grid_cell]
            base_id = f"{PREFIX}-{grid_cell}-{encode_counter(counter)}"
            while base_id in used_ids:
                counter += 1
                base_id = f"{PREFIX}-{grid_cell}-{encode_counter(counter)}"

            grp['base_id'] = base_id
            grp['inherited'] = False
            grp['match_quality'] = f"new {version}"
            used_ids.add(base_id)
            grid_counters[grid_cell] = counter + 1

            best = max(grp['l2_candidates'], key=lambda t: t[1]['area'],
                       default=None)
            poor_matches.append({
                'group_id': grp['group_id'],
                'base_id': base_id,
                'reason': 'pool loser' if best else 'no candidates',
                'share_old': best[1]['share_old'] if best else None,
                'share_new': best[1]['share_new'] if best else None,
                'best_prev_id': (
                    str(prev_l2_m.iloc[best[0]]['ReefID']) if best else ''
                ),
                'geometry': grp['geometry']
            })

    # Assign sub-feature letters with matching against previous L3. This also
    # records per-feature lineage and inherits previous-version
    # PrevReefID/ReefIDNote values (both gated by the sliver + share test),
    # stored on each group for the write loop in main().
    assign_letters_matched(groups, gdf_m, prev_l3_m)

    return groups, poor_matches


def assign_letters_matched(groups, gdf_m, prev_l3_m):
    """
    Assign sub-feature letters by matching against previous L3 features, with a
    shared letter pool per base ID. Also records per-feature lineage
    (PrevReefID source IDs) and inherits previous-version PrevReefID/ReefIDNote
    values, both gated by the sliver + share test in the matching CRS.
    """
    def generate_suffix(index):
        """Generate suffix (single or multi-letter) for a given index."""
        suffix = ""
        while index >= 0:
            suffix = chr(ord('a') + (index % 26)) + suffix
            index = (index // 26) - 1
        return suffix

    def next_letter(used_letters, retired_letters):
        """Next available letter suffix, skipping letters allocated in this run
        and letters retired in the previous version."""
        i = 0
        while True:
            letter = generate_suffix(i)
            if letter not in used_letters and letter not in retired_letters:
                return letter
            i += 1

    # Build lookup: base_id -> list of (letter, geometry, reef_id) from previous L3
    prev_letters = {}
    if 'ReefID' in prev_l3_m.columns:
        for idx, row in prev_l3_m.iterrows():
            rid = row['ReefID']
            if pd.isna(rid) or rid == '':
                continue
            rid = str(rid)
            base = strip_suffix(rid)
            # Extract suffix (may be multi-letter, e.g. 'aa', 'ab')
            letter = rid[len(base):] if rid != base else None
            if base not in prev_letters:
                prev_letters[base] = []
            prev_letters[base].append({
                'letter': letter,
                'geometry': row.geometry,
                'reef_id': rid
            })

    # ---- Per-feature pass: sliver + share test against all previous L3 ----
    # For every current feature, find previous L3 features whose intersection
    # survives the sliver test and reaches CANDIDATE_SHARE. From these:
    #   - lineage IDs (recorded in PrevReefID for features receiving a new ID)
    #   - inherited PrevReefID/ReefIDNote values (from the best-passing feature)
    feat_prev_ids = {}    # idx -> set of passing previous ReefIDs
    inherited_prev = {}   # idx -> set of previous-version PrevReefID values
    inherited_notes = {}  # idx -> set of previous-version ReefIDNote values
    prev_l3_sindex = prev_l3_m.sindex
    if 'ReefID' in prev_l3_m.columns:
        has_prev_val = 'PrevReefID' in prev_l3_m.columns
        has_note = 'ReefIDNote' in prev_l3_m.columns
        for grp in groups:
            for idx in grp['member_indices']:
                feat_geom = gdf_m.loc[idx, 'geometry']
                passing = []
                for pos in prev_l3_sindex.intersection(feat_geom.bounds):
                    scored = score_pair(feat_geom, prev_l3_m.geometry.iloc[pos])
                    if not is_candidate(scored):
                        continue
                    passing.append((scored['area'], pos))
                if not passing:
                    continue
                for _area, pos in passing:
                    prev_id = prev_l3_m.iloc[pos]['ReefID']
                    if pd.notna(prev_id) and prev_id != '':
                        feat_prev_ids.setdefault(idx, set()).add(str(prev_id))
                best = max(passing, key=lambda t: t[0])[1]
                if has_prev_val:
                    prev_val = prev_l3_m.iloc[best].get('PrevReefID', '')
                    if pd.notna(prev_val) and prev_val != '':
                        inherited_prev.setdefault(idx, set()).update(
                            str(prev_val).split('; '))
                if has_note:
                    prev_note = prev_l3_m.iloc[best].get('ReefIDNote', '')
                    if pd.notna(prev_note) and prev_note != '':
                        inherited_notes.setdefault(idx, set()).update(
                            str(prev_note).split('; '))

    # Expose for the write loop in main()
    for grp in groups:
        grp['inherited_prev'] = {
            idx: inherited_prev.get(idx, set()) for idx in grp['member_indices']
        }
        grp['inherited_notes'] = {
            idx: inherited_notes.get(idx, set()) for idx in grp['member_indices']
        }

    # ---- Letter assignment with per-base shared pool ----
    groups_by_base = {}
    for grp in groups:
        groups_by_base.setdefault(grp['base_id'], []).append(grp)

    for base_id, base_groups in groups_by_base.items():
        # Largest groups first: the first to claim the unsuffixed form keeps it,
        # and letters are allocated deterministically across the base.
        base_groups.sort(key=lambda g: -g['geom_match'].area)
        prev_entries = prev_letters.get(base_id, [])
        # Letters allocated in this run to any group of this base
        used_letters = set()
        # Letters retired in the previous version (reserved, never reassigned)
        retired_letters = {e['letter'] for e in prev_entries if e['letter']}
        unsuffixed_claimed = False

        for grp in base_groups:
            members = grp['member_indices']
            base = grp['base_id']
            grp['feature_notes'] = {}
            grp['prev_reef_ids'] = {}

            if len(members) == 1:
                idx = members[0]
                if not unsuffixed_claimed:
                    # Single component: no letter suffix
                    grp['feature_ids'] = {idx: base}
                    unsuffixed_claimed = True
                else:
                    # Another group of this base takes the unsuffixed form,
                    # so this one receives a letter
                    letter = next_letter(used_letters, retired_letters)
                    used_letters.add(letter)
                    grp['feature_ids'] = {idx: f"{base}{letter}"}
                # Lineage: the write loop discards self-references, so this
                # is a no-op for features that kept their own ID and records
                # the previous source ID(s) for those that did not
                grp['prev_reef_ids'][idx] = feat_prev_ids.get(idx, set())
            else:
                # Multi-component: try to match by overlap with previous letters
                grp['feature_ids'] = {}
                matched_features = {}

                # If previous was single (no letters), the original gets unsuffixed ID
                was_single = (len(prev_entries) == 1
                              and prev_entries[0]['letter'] is None)
                if was_single:
                    # Reserve 'a' so new suffixes start from 'b'
                    retired_letters.add('a')

                if prev_entries and not was_single:
                    # Match current features to previous by overlap. A feature
                    # may match a previous letter unless another current feature
                    # of this base has already claimed it.
                    for idx in members:
                        feat_geom = gdf_m.loc[idx, 'geometry']
                        best_overlap = 0
                        best_letter = None

                        for entry in prev_entries:
                            if entry['letter'] is None:
                                continue
                            if entry['letter'] in used_letters:
                                continue
                            try:
                                intersection = feat_geom.intersection(entry['geometry'])
                                overlap = intersection.area
                            except Exception:
                                continue
                            feat_area = feat_geom.area
                            ratio = overlap / feat_area if feat_area > 0 else 0
                            if ratio > LETTER_MATCH_SHARE and overlap > best_overlap:
                                best_overlap = overlap
                                best_letter = entry['letter']

                        if best_letter:
                            # Keeps its previous ID: no new lineage
                            matched_features[idx] = best_letter
                            used_letters.add(best_letter)
                            grp['prev_reef_ids'][idx] = set()
                        else:
                            # Unmatched: new letter, with lineage recorded
                            # (non-exclusive: several features may reference
                            # the same previous feature)
                            matched_features[idx] = None  # placeholder
                            grp['prev_reef_ids'][idx] = feat_prev_ids.get(idx, set())
                            grp['feature_notes'][idx] = f"new {version}"

                    # Assign letters to the unmatched features from the shared pool,
                    # in area-descending order
                    unmatched_areas = [
                        (idx, gdf_m.loc[idx, 'geometry'].area)
                        for idx in members
                        if idx in matched_features and matched_features[idx] is None
                    ]
                    unmatched_areas.sort(key=lambda x: -x[1])
                    for idx, _ in unmatched_areas:
                        letter = next_letter(used_letters, retired_letters)
                        matched_features[idx] = letter
                        used_letters.add(letter)

                elif was_single:
                    # Previously single, now multi: identify the original
                    # feature by spatial overlap; it keeps the unsuffixed ID.
                    # New features get letter suffixes.
                    prev_geom = prev_entries[0]['geometry']
                    best_idx = None
                    best_overlap = 0
                    for idx in members:
                        feat_geom = gdf_m.loc[idx, 'geometry']
                        try:
                            overlap = feat_geom.intersection(prev_geom).area
                        except Exception:
                            overlap = 0
                        if overlap > best_overlap:
                            best_overlap = overlap
                            best_idx = idx

                    # Original feature keeps unsuffixed base_id (None = no letter)
                    if best_idx is not None:
                        if not unsuffixed_claimed:
                            matched_features[best_idx] = None
                            unsuffixed_claimed = True
                        else:
                            letter = next_letter(used_letters, retired_letters)
                            used_letters.add(letter)
                            matched_features[best_idx] = letter
                        grp['prev_reef_ids'][best_idx] = set()
                    # New features: split fragments record the previous feature
                    # they were carved from; genuine additions record nothing.
                    # Letters in area-descending order.
                    new_areas = [
                        (idx, gdf_m.loc[idx, 'geometry'].area)
                        for idx in members if idx != best_idx
                    ]
                    new_areas.sort(key=lambda x: -x[1])
                    for idx, _ in new_areas:
                        letter = next_letter(used_letters, retired_letters)
                        used_letters.add(letter)
                        matched_features[idx] = letter
                        grp['prev_reef_ids'][idx] = feat_prev_ids.get(idx, set())
                        grp['feature_notes'][idx] = f"new {version}"

                else:
                    # No previous entries (new base): all features are new;
                    # letters by area descending
                    for idx in members:
                        grp['prev_reef_ids'][idx] = feat_prev_ids.get(idx, set())
                        grp['feature_notes'][idx] = f"new {version}"
                    new_areas = [
                        (idx, gdf_m.loc[idx, 'geometry'].area) for idx in members
                    ]
                    new_areas.sort(key=lambda x: -x[1])
                    for idx, _ in new_areas:
                        letter = next_letter(used_letters, retired_letters)
                        used_letters.add(letter)
                        matched_features[idx] = letter

                # Build final ReefIDs
                for idx, letter in matched_features.items():
                    if letter is None:
                        # Original feature from was_single: keep unsuffixed
                        grp['feature_ids'][idx] = base
                    else:
                        grp['feature_ids'][idx] = f"{base}{letter}"

    return groups


def main():
    parser = argparse.ArgumentParser(
        description="Allocate permanent ReefIDs to reef features."
    )
    parser.add_argument(
        '--fresh', action='store_true',
        help='Allocate all IDs from scratch (no matching against previous version).'
    )
    args = parser.parse_args()

    # Create output directory
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Load input features
    print("Reading input shapefile...")
    gdf = gpd.read_file(INPUT_SHP)
    print(f"  Loaded {len(gdf)} features.")

    # Explode multiparts to singleparts
    original_count = len(gdf)
    gdf = gdf.explode(index_parts=False).reset_index(drop=True)
    if len(gdf) != original_count:
        print(f"  Exploded multiparts: {original_count} -> {len(gdf)} features.")

    # Ensure CRS is EPSG:4326 for grid encoding
    if gdf.crs and str(gdf.crs) != "EPSG:4326":
        gdf_4326 = gdf.to_crs(epsg=4326)
    else:
        gdf_4326 = gdf

    # Load crosswalk
    print("Reading crosswalk table...")
    crosswalk = pd.read_csv(CROSSWALK_CSV, dtype=str).fillna('')
    print(f"  Loaded {len(crosswalk)} crosswalk rows.")

    # Build L2 groups (using 4326 geometry for spatial operations)
    print("Building L2 groups (dissolving touching same-L2-class features)...")
    groups, feature_to_group = build_l2_groups(gdf_4326, crosswalk)
    print(f"  Formed {len(groups)} L2 groups from {len(gdf)} features.")

    # Allocate ReefIDs
    if args.fresh:
        print("Allocating ReefIDs from scratch (--fresh mode)...")
        groups = allocate_fresh(groups, gdf_4326)
        poor_matches = []
    else:
        # Check previous version files exist
        if not PREVIOUS_L2 or not os.path.exists(PREVIOUS_L2):
            raise FileNotFoundError(
                f"Previous L2 output not found: {PREVIOUS_L2}. "
                f"Use --fresh for first-time allocation."
            )
        if not PREVIOUS_L3 or not os.path.exists(PREVIOUS_L3):
            raise FileNotFoundError(
                f"Previous L3 output not found: {PREVIOUS_L3}. "
                f"Use --fresh for first-time allocation."
            )

        print(f"Loading previous L2: {PREVIOUS_L2}")
        prev_l2_gdf = gpd.read_file(PREVIOUS_L2)
        print(f"  Loaded {len(prev_l2_gdf)} previous L2 features.")

        print(f"Loading previous L3: {PREVIOUS_L3}")
        prev_l3_gdf = gpd.read_file(PREVIOUS_L3)
        print(f"  Loaded {len(prev_l3_gdf)} previous L3 features.")

        print("Matching against previous version...")
        groups, poor_matches = allocate_matched(
            groups, gdf_4326, prev_l2_gdf, prev_l3_gdf
        )

    # Apply ReefIDs back to the original GeoDataFrame
    print("Writing ReefIDs to features...")
    gdf['ReefID'] = ''
    gdf['PrevReefID'] = ''
    gdf['ReefIDNote'] = ''

    for grp in groups:
        if 'feature_ids' not in grp:
            continue
        for idx, reef_id in grp['feature_ids'].items():
            gdf.at[idx, 'ReefID'] = reef_id
        # Build accumulated PrevReefID sets (inherited values + recorded lineage)
        if 'prev_reef_ids' in grp:
            inherited_prev = grp.get('inherited_prev', {})
            for idx in grp['member_indices']:
                prev_set = set(inherited_prev.get(idx, set()))
                prev_set |= grp['prev_reef_ids'].get(idx, set())
                # Remove current ReefID from set (not useful as self-reference)
                current_id = grp['feature_ids'].get(idx, '')
                prev_set.discard(current_id)
                if prev_set:
                    gdf.at[idx, 'PrevReefID'] = '; '.join(sorted(prev_set))
        # Add match quality note for new groups (all members are new)
        if 'match_quality' in grp:
            if grp['match_quality'].startswith('new'):
                for idx in grp['member_indices']:
                    grp.setdefault('feature_notes', {})[idx] = grp['match_quality']
        # Build accumulated ReefIDNote sets (inherit from previous + add new)
        inherited_notes = grp.get('inherited_notes', {})
        feature_notes = grp.get('feature_notes', {})
        for idx in grp['member_indices']:
            note_set = set(inherited_notes.get(idx, set()))
            new_note = feature_notes.get(idx, '')
            if new_note:
                note_set.add(new_note)
            if note_set:
                gdf.at[idx, 'ReefIDNote'] = '; '.join(sorted(note_set))

    # Verify all features have ReefIDs
    missing = gdf[gdf['ReefID'] == '']
    if not missing.empty:
        print(f"  WARNING: {len(missing)} features have no ReefID assigned!")

    # Verify ReefID uniqueness (a duplicate indicates a matching/lettering error)
    dup_mask = gdf['ReefID'].duplicated(keep=False) & (gdf['ReefID'] != '')
    dupes = gdf[dup_mask]
    if not dupes.empty:
        dup_ids = sorted(dupes['ReefID'].unique())
        raise RuntimeError(
            f"Duplicate ReefIDs detected: {len(dupes)} features share "
            f"{len(dup_ids)} IDs: {dup_ids[:20]}"
        )

    # Save output shapefile
    print(f"Saving output to {OUTPUT_SHP}...")
    gdf.to_file(OUTPUT_SHP)

    # Save poor-match QA shapefile
    if poor_matches:
        print(f"Saving {len(poor_matches)} poor-match groups to {POOR_MATCH_SHP}...")
        pm_gdf = gpd.GeoDataFrame(poor_matches, crs=gdf.crs)
        pm_gdf.to_file(POOR_MATCH_SHP)
    else:
        print("No poor matches to report.")

    # Write allocation log
    print(f"Writing allocation log to {ALLOCATION_LOG}...")
    log_records = []
    for grp in groups:
        if 'feature_ids' not in grp:
            continue
        for idx, reef_id in grp['feature_ids'].items():
            log_records.append({
                'feature_index': idx,
                'ReefID': reef_id,
                'base_id': grp['base_id'],
                'group_id': grp['group_id'],
                'l2_class': grp['l2_class'],
                'grid_cell': grp['grid_cell'],
                'match_quality': grp.get('match_quality', 'fresh'),
                'n_members': len(grp['member_indices']),
            })
    log_df = pd.DataFrame(log_records)
    log_df.to_csv(ALLOCATION_LOG, index=False)

    # Summary
    n_groups = len(groups)
    n_features = len(gdf)
    n_single = sum(1 for g in groups if len(g['member_indices']) == 1)
    n_multi = n_groups - n_single
    print(f"\nSummary:")
    print(f"  Total features: {n_features}")
    print(f"  Total L2 groups (reefs): {n_groups}")
    print(f"  Single-component reefs: {n_single}")
    print(f"  Multi-component reefs: {n_multi}")
    if poor_matches:
        n_losers = sum(1 for p in poor_matches if p['reason'] == 'pool loser')
        print(f"  Non-inheriting groups flagged: {len(poor_matches)} "
              f"({n_losers} pool losers)")
    print("Done.")


if __name__ == "__main__":
    main()
