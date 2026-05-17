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
    6. Otherwise, load previous L2 and L3 outputs and match spatially.
    7. Assign sub-feature letters within each group.
    8. Write output shapefile with ReefID, PrevReefID, ReefIDNote fields.
       PrevReefID is a semicolon-separated set that accumulates across versions.

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
import re

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.ops import unary_union

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

# Overlap threshold for spatial matching
OVERLAP_THRESHOLD = 0.50


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
    """
    # Compute centroids and grid cells for current groups
    for grp in groups:
        centroid = grp['geometry'].centroid
        grp['centroid_lon'] = centroid.x
        grp['centroid_lat'] = centroid.y
        grp['grid_cell'] = encode_grid(centroid.x, centroid.y)
        grp['centroid_sum'] = centroid.x + centroid.y

    # Build set of all existing IDs in previous version
    prev_base_ids = set()
    if 'ReefID' in prev_l2_gdf.columns:
        for rid in prev_l2_gdf['ReefID'].dropna():
            prev_base_ids.add(strip_suffix(str(rid)))
    elif 'ReefID' in prev_l3_gdf.columns:
        for rid in prev_l3_gdf['ReefID'].dropna():
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

    # Spatial matching: for each current group, find best overlap with previous L2
    poor_matches = []
    used_ids = set(prev_base_ids)

    # Ensure CRS alignment
    if prev_l2_gdf.crs != gdf.crs:
        prev_l2_gdf = prev_l2_gdf.to_crs(gdf.crs)
    if prev_l3_gdf.crs != gdf.crs:
        prev_l3_gdf = prev_l3_gdf.to_crs(gdf.crs)

    # Build spatial index for previous L2
    prev_l2_sindex = prev_l2_gdf.sindex

    for grp in groups:
        grp_geom = grp['geometry']
        grp_area = grp_geom.area

        # Check manual override first
        override_id = None
        for idx in grp['member_indices']:
            feat_id = gdf.at[idx, 'ReefID'] if 'ReefID' in gdf.columns else None
            if pd.notna(feat_id) and feat_id != '':
                override_id = strip_suffix(str(feat_id))
                break

        if override_id:
            grp['base_id'] = override_id
            grp['match_quality'] = 'override'
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

        # Find candidate previous L2 features by spatial index
        candidates_idx = list(prev_l2_sindex.intersection(grp_geom.bounds))
        best_overlap = 0
        best_prev_id = None

        for cidx in candidates_idx:
            prev_geom = prev_l2_gdf.geometry.iloc[cidx]
            try:
                intersection = grp_geom.intersection(prev_geom)
                overlap_area = intersection.area
            except Exception:
                continue

            if overlap_area > best_overlap:
                best_overlap = overlap_area
                if 'ReefID' in prev_l2_gdf.columns:
                    best_prev_id = prev_l2_gdf.iloc[cidx]['ReefID']

        overlap_ratio = best_overlap / grp_area if grp_area > 0 else 0

        if overlap_ratio > OVERLAP_THRESHOLD and best_prev_id and pd.notna(best_prev_id):
            # Good match: inherit previous ID
            grp['base_id'] = strip_suffix(str(best_prev_id))
            grp['match_quality'] = f"matched ({overlap_ratio:.1%})"
            used_ids.add(grp['base_id'])
        else:
            # Poor match: allocate new ID
            grid_cell = grp['grid_cell']
            if grid_cell not in grid_counters:
                grid_counters[grid_cell] = 0

            counter = grid_counters[grid_cell]
            base_id = f"{PREFIX}-{grid_cell}-{encode_counter(counter)}"
            while base_id in used_ids:
                counter += 1
                base_id = f"{PREFIX}-{grid_cell}-{encode_counter(counter)}"

            grp['base_id'] = base_id
            grp['match_quality'] = f"new {version}"
            used_ids.add(base_id)
            grid_counters[grid_cell] = counter + 1

            poor_matches.append({
                'group_id': grp['group_id'],
                'base_id': base_id,
                'overlap_ratio': overlap_ratio,
                'best_prev_id': best_prev_id if best_prev_id and pd.notna(best_prev_id) else '',
                'geometry': grp_geom
            })

    # Assign sub-feature letters with matching against previous L3
    assign_letters_matched(groups, gdf, prev_l3_gdf)

    return groups, poor_matches


def assign_letters_matched(groups, gdf, prev_l3_gdf):
    """
    Assign sub-feature letters by matching against previous L3 features.
    Also populates per-feature 'feature_notes' on each group.
    """
    def generate_suffix(index):
        """Generate suffix (single or multi-letter) for a given index."""
        suffix = ""
        while index >= 0:
            suffix = chr(ord('a') + (index % 26)) + suffix
            index = (index // 26) - 1
        return suffix

    def _best_overlap_prev_id(feat_geom, prev_entries):
        """Find the previous feature with the best area overlap (non-exclusive).
        Returns the previous ReefID or '' if no overlap found."""
        best_overlap = 0
        best_prev_id = ''
        for entry in prev_entries:
            try:
                overlap = feat_geom.intersection(entry['geometry']).area
            except Exception:
                continue
            if overlap > best_overlap:
                best_overlap = overlap
                best_prev_id = entry['reef_id']
        return best_prev_id

    # Build lookup: base_id -> list of (letter, geometry) from previous L3
    prev_letters = {}
    if 'ReefID' in prev_l3_gdf.columns:
        for idx, row in prev_l3_gdf.iterrows():
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

    for grp in groups:
        members = grp['member_indices']
        base_id = grp['base_id']
        grp['feature_notes'] = {}  # per-feature notes

        if len(members) == 1:
            # Check if previously this was multi-component
            prev_entries = prev_letters.get(base_id, [])
            if len(prev_entries) > 1:
                # Was multi-component, now single: revert to unsuffixed
                grp['feature_ids'] = {members[0]: base_id}
                # Find which previous sub-feature best overlaps this one
                feat_geom = gdf.loc[members[0], 'geometry']
                best_prev_id = _best_overlap_prev_id(feat_geom, prev_entries)
                grp['prev_reef_ids'] = {members[0]: best_prev_id}
            else:
                grp['feature_ids'] = {members[0]: base_id}
                grp['prev_reef_ids'] = {members[0]: ''}
        else:
            # Multi-component: try to match by overlap with previous letters
            prev_entries = prev_letters.get(base_id, [])
            grp['feature_ids'] = {}
            grp['prev_reef_ids'] = {}
            used_letters = set()
            matched_features = {}

            # If previous was single (no letters), the original gets unsuffixed ID
            was_single = (len(prev_entries) == 1 and prev_entries[0]['letter'] is None)

            if prev_entries and not was_single:
                # Match current features to previous by overlap
                for idx in members:
                    feat_geom = gdf.loc[idx, 'geometry']
                    best_overlap = 0
                    best_letter = None

                    for entry in prev_entries:
                        if entry['letter'] in used_letters:
                            continue
                        try:
                            intersection = feat_geom.intersection(entry['geometry'])
                            overlap = intersection.area
                        except Exception:
                            continue
                        feat_area = feat_geom.area
                        ratio = overlap / feat_area if feat_area > 0 else 0
                        if ratio > OVERLAP_THRESHOLD and overlap > best_overlap:
                            best_overlap = overlap
                            best_letter = entry['letter']

                    if best_letter:
                        matched_features[idx] = best_letter
                        used_letters.add(best_letter)
                        grp['prev_reef_ids'][idx] = ''
                    else:
                        # Unmatched: find best-overlapping previous feature
                        # for lineage tracking (non-exclusive)
                        best_prev_id = _best_overlap_prev_id(
                            gdf.loc[idx, 'geometry'], prev_entries
                        )
                        grp['prev_reef_ids'][idx] = best_prev_id
                        grp['feature_notes'][idx] = f"new {version}"

                # Collect used letters from previous (for gap preservation)
                for entry in prev_entries:
                    if entry['letter']:
                        used_letters.add(entry['letter'])

            elif was_single:
                # Previously single, now multi: identify the original
                # feature by spatial overlap; it keeps the unsuffixed ID.
                # New features get letter suffixes.
                prev_geom = prev_entries[0]['geometry']
                best_idx = None
                best_overlap = 0
                for idx in members:
                    feat_geom = gdf.loc[idx, 'geometry']
                    try:
                        overlap = feat_geom.intersection(prev_geom).area
                    except Exception:
                        overlap = 0
                    if overlap > best_overlap:
                        best_overlap = overlap
                        best_idx = idx

                # Original feature keeps unsuffixed base_id (None = no letter)
                if best_idx is not None:
                    matched_features[best_idx] = None
                    grp['prev_reef_ids'][best_idx] = ''
                # New features: no PrevReefID (they are genuinely new)
                for idx in members:
                    if idx != best_idx:
                        grp['prev_reef_ids'].setdefault(idx, '')
                        grp['feature_notes'][idx] = f"new {version}"
                # Reserve 'a' so new suffixes start from 'b'
                used_letters.add('a')

            # Assign letters to unmatched features
            next_suffix_idx = 0
            unmatched = [idx for idx in members if idx not in matched_features]
            # Sort unmatched by area descending
            unmatched_areas = [(idx, gdf.loc[idx, 'geometry'].area) for idx in unmatched]
            unmatched_areas.sort(key=lambda x: -x[1])

            for idx, _ in unmatched_areas:
                letter = generate_suffix(next_suffix_idx)
                while letter in used_letters:
                    next_suffix_idx += 1
                    letter = generate_suffix(next_suffix_idx)
                matched_features[idx] = letter
                used_letters.add(letter)
                next_suffix_idx += 1

            # Build final ReefIDs
            for idx, letter in matched_features.items():
                if letter is None:
                    # Original feature from was_single: keep unsuffixed
                    grp['feature_ids'][idx] = base_id
                else:
                    grp['feature_ids'][idx] = f"{base_id}{letter}"


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
    poor_matches = []
    if args.fresh:
        print("Allocating ReefIDs from scratch (--fresh mode)...")
        groups = allocate_fresh(groups, gdf_4326)
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

    # Build inherited PrevReefID and ReefIDNote sets from previous L3 output
    inherited_prev = {}  # feature index -> set of previous IDs
    inherited_notes = {}  # feature index -> set of previous notes
    has_prev_fields = (not args.fresh and
                       ('PrevReefID' in prev_l3_gdf.columns or
                        'ReefIDNote' in prev_l3_gdf.columns))
    if has_prev_fields:
        # Build spatial index for previous L3
        prev_l3_sindex = prev_l3_gdf.sindex
        for grp in groups:
            if 'feature_ids' not in grp:
                continue
            for idx in grp['member_indices']:
                feat_geom = gdf_4326.loc[idx, 'geometry']
                candidates = list(prev_l3_sindex.intersection(feat_geom.bounds))
                best_overlap = 0
                best_cidx = None
                for cidx in candidates:
                    try:
                        overlap = feat_geom.intersection(
                            prev_l3_gdf.geometry.iloc[cidx]
                        ).area
                    except Exception:
                        continue
                    if overlap > best_overlap:
                        best_overlap = overlap
                        best_cidx = cidx
                if best_cidx is not None:
                    prev_val = prev_l3_gdf.iloc[best_cidx].get('PrevReefID', '')
                    if pd.notna(prev_val) and prev_val != '':
                        inherited_prev[idx] = set(str(prev_val).split('; '))
                    prev_note = prev_l3_gdf.iloc[best_cidx].get('ReefIDNote', '')
                    if pd.notna(prev_note) and prev_note != '':
                        inherited_notes[idx] = set(str(prev_note).split('; '))

    for grp in groups:
        if 'feature_ids' not in grp:
            continue
        for idx, reef_id in grp['feature_ids'].items():
            gdf.at[idx, 'ReefID'] = reef_id
        # Build accumulated PrevReefID sets
        if 'prev_reef_ids' in grp:
            for idx, prev_id in grp['prev_reef_ids'].items():
                prev_set = set(inherited_prev.get(idx, set()))
                if prev_id:
                    prev_set.add(prev_id)
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
        print(f"  Poor matches flagged: {len(poor_matches)}")
    print("Done.")


if __name__ == "__main__":
    main()
