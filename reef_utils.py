"""
Module: reef_utils.py

Shared utilities for reef processing scripts.

Provides consistent L2 dissolve/clustering logic used by both
11-allocate-ReefIDs.py and 13-make-RB_Type_L2.py to prevent
discrepancies in how features are grouped at the L2 level.

The key operations are:
    - Geometry cleaning (buffer(0)) to fix invalid topologies
    - Dissolve by RB_Type_L2 class via unary_union
    - Sliver repair (buffer(+eps).buffer(-eps)) to close floating-point
      precision gaps along feature boundaries
    - Consistent spatial join to assign original features to dissolved components
"""

import re

import geopandas as gpd
from shapely.ops import unary_union

# Small buffer (degrees) used to close floating-point slivers/gaps after dissolve.
# Applied as buffer(+eps).buffer(-eps): the outward pass seals sub-pixel holes along
# internal seams; the inward pass restores the outer boundary to its original extent.
# At these latitudes (~15-25S), 1e-6 degrees ~ 0.1 m.
SLIVER_EPS = 1e-6


def strip_reef_suffix(reef_id):
    """Strip trailing lowercase letter suffix from a ReefID to get the base form.

    Handles both single-letter (a-z) and multi-letter (aa, ab, etc.) suffixes
    produced by the ReefID allocation scheme.

    Examples:
        'R-8238-367a'  -> 'R-8238-367'
        'R-8238-367aa' -> 'R-8238-367'
        'R-8238-367'   -> 'R-8238-367'
    """
    if reef_id:
        return re.sub(r'[a-z]+$', '', str(reef_id))
    return reef_id


def dissolve_to_l2_components(gdf):
    """
    Dissolve features by RB_Type_L2 into singlepart components.

    Applies geometry cleaning (buffer(0)) and sliver repair
    (buffer(+eps).buffer(-eps)) to ensure consistent grouping regardless
    of floating-point precision artifacts at feature boundaries.

    Parameters
    ----------
    gdf : GeoDataFrame
        Must contain 'RB_Type_L2' column and geometry.

    Returns
    -------
    list of dict
        Each dict has:
        - 'l2_class': str - the RB_Type_L2 class
        - 'geometry': shapely geometry - the dissolved singlepart polygon
        - 'member_indices': list of int - original feature indices in this component
    """
    # Clean geometries to fix invalid topologies
    gdf = gdf.copy()
    gdf['geometry'] = gdf.geometry.buffer(0)
    gdf = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty].copy()

    components = []

    for l2_class, class_gdf in gdf.groupby('RB_Type_L2'):
        # Union all features of this L2 class
        union_geom = unary_union(class_gdf.geometry)
        # Close floating-point slivers/gaps produced by the dissolve
        union_geom = union_geom.buffer(SLIVER_EPS).buffer(-SLIVER_EPS)
        # Remove redundant micro-vertices introduced by the buffer arcs
        union_geom = union_geom.simplify(SLIVER_EPS, preserve_topology=True)
        # Explode into singlepart components (each = one reef)
        parts_gdf = gpd.GeoDataFrame(
            geometry=[union_geom], crs=gdf.crs
        ).explode(index_parts=False).reset_index(drop=True)
        parts_gdf['_part_id'] = range(len(parts_gdf))

        # Assign each original feature to its dissolved group via representative_point.
        # representative_point() is guaranteed to lie within the feature polygon,
        # making it robust for within-polygon matching.
        feat_points = class_gdf.copy()
        feat_points['_orig_idx'] = feat_points.index
        feat_points['geometry'] = feat_points.geometry.representative_point()

        joined = gpd.sjoin(
            feat_points[['_orig_idx', 'geometry']],
            parts_gdf[['_part_id', 'geometry']],
            predicate='within',
            how='left'
        )

        # Handle features whose representative_point didn't fall within any part
        # (rare floating-point edge case): fall back to intersects with original geometry
        unassigned = joined[joined['_part_id'].isna()]
        if not unassigned.empty:
            unassigned_indices = unassigned['_orig_idx'].tolist()
            unassigned_feats = class_gdf.loc[unassigned_indices].copy()
            unassigned_feats['_orig_idx'] = unassigned_feats.index

            fallback_join = gpd.sjoin(
                unassigned_feats[['_orig_idx', 'geometry']],
                parts_gdf[['_part_id', 'geometry']],
                predicate='intersects',
                how='left'
            )
            # Drop duplicates (feature might intersect multiple parts; take first)
            fallback_join = fallback_join.drop_duplicates(subset='_orig_idx')

            # Update the main joined dataframe with fallback assignments
            for _, row in fallback_join.iterrows():
                mask = joined['_orig_idx'] == row['_orig_idx']
                joined.loc[mask, '_part_id'] = row['_part_id']

        # Still unassigned after fallback (should not happen but be safe)
        still_unassigned = joined[joined['_part_id'].isna()]
        if not still_unassigned.empty:
            print(f"  WARNING: {len(still_unassigned)} features of class '{l2_class}' "
                  f"could not be assigned to any dissolved component.")

        for part_id, part_feats in joined.dropna(subset=['_part_id']).groupby('_part_id'):
            member_indices = part_feats['_orig_idx'].tolist()
            part_geom = parts_gdf.loc[
                parts_gdf['_part_id'] == int(part_id), 'geometry'
            ].iloc[0]

            components.append({
                'l2_class': l2_class,
                'geometry': part_geom,
                'member_indices': member_indices,
            })

    return components
