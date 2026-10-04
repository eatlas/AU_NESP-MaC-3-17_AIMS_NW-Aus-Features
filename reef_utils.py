"""
Module: reef_utils.py

Shared utilities for reef processing scripts.

Provides consistent L2 dissolve/clustering logic used by
11-allocate-ReefIDs.py and 13-make-RB_Type_L2.py to prevent
discrepancies in how features are grouped at the L2 level, plus
countable-reef clustering used by A04-reef-progression.py.

The key operations are:
    - Geometry cleaning (buffer(0)) to fix invalid topologies
    - Dissolve by RB_Type_L2 class via unary_union
    - Sliver repair (buffer(+eps).buffer(-eps)) to close floating-point
      precision gaps along feature boundaries
    - Consistent spatial join to assign original features to dissolved components
    - cluster_countable(): buffer-based grouping of fused reefs into
      countable clusters
"""

import re

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import MultiPolygon, Polygon
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


def cluster_countable(gdf, buffer_m=50.0, min_width_m=100.0, drop_small=True,
                      size_classes=None, buffer_crs=3112, show_progress=False):
    """
    Cluster fused reefs into "countable reefs".

    Grouping: each reef is buffered by buffer_m (in buffer_crs) and the
    buffers are unary-unioned per RB_Type_L2 class, so reefs within the
    buffer of each other merge into a single cluster only with reefs of
    the same type. The buffer is used ONLY to determine the grouping;
    it does not enter any measurement.

    Measurement: each cluster is mapped back to its original (unbuffered)
    member reefs, whose geometries are unioned (closely clustered reefs
    form multi-part polygons). The cluster's area and effective width are
    computed from that unbuffered union, so areas are true reef areas.
    Clusters with an effective width below min_width_m are dropped when
    drop_small is True; the survivors may be binned into size classes.

    Parameters
    ----------
    gdf : GeoDataFrame
        Fused reefs (e.g. the output of A04-reef-progression.py's
        process_version, before size classification). Must contain an
        'RB_Type_L2' column and Polygon/MultiPolygon geometries in a
        non-null CRS.
    buffer_m : float
        Buffer distance in metres (in buffer_crs), used only to decide
        the grouping.
    min_width_m : float
        Effective width (m, diameter of an equal-area circle) below
        which a cluster is not "countable".
    drop_small : bool
        If True (default), clusters with effective width below min_width_m
        are dropped; if False they are retained.
    size_classes : list of (name, lo_m, hi_m) or None
        If given, an 'SizeClass' column is added (lo inclusive, hi
        exclusive). If None, no size class is calculated.
    buffer_crs : int or pyproj.CRS
        Projected (metre) CRS in which the buffer and union are computed.
        Defaults to EPSG:3112 (MGRUP, covers Australia). The output is
        returned in the input CRS.
    show_progress : bool
        Print per-class clustering milestones and the number of clusters
        processed when True. Off by default for existing callers.

    Returns
    -------
    (GeoDataFrame, dict)
        The countable reefs (in the input CRS) with 'RB_Type_L2',
        'Area_km2', 'EffWidth_m' and (if size_classes was given)
        'SizeClass', plus a stats dict with keys 'n_fused',
        'n_clusters', 'n_dropped', 'n_countable', 'n_unassigned' and
        'n_by_class'.
    """
    if not isinstance(gdf, gpd.GeoDataFrame):
        raise TypeError(f"gdf must be a GeoDataFrame, got {type(gdf).__name__}")
    if 'RB_Type_L2' not in gdf.columns:
        raise ValueError(
            "gdf must contain an 'RB_Type_L2' column: each reef's L2 class "
            "is required for the per-class clustering. "
            f"Columns present: {list(gdf.columns)}"
        )
    if gdf.crs is None:
        raise ValueError(
            "gdf must have a non-null CRS (the output is returned in the "
            "input CRS)."
        )
    n_null_class = int(gdf['RB_Type_L2'].isna().sum())
    if n_null_class:
        raise ValueError(f"{n_null_class} features have a null RB_Type_L2")
    bad_geoms = gdf.geometry[
        ~gdf.geometry.apply(lambda g: isinstance(g, (Polygon, MultiPolygon)))
    ]
    if not bad_geoms.empty:
        kinds = sorted(bad_geoms.geom_type.unique())
        raise ValueError(
            f"gdf must contain only Polygon/MultiPolygon geometries, found "
            f"{len(bad_geoms)} of type {kinds}"
        )
    if buffer_m < 0:
        raise ValueError(f"buffer_m must be >= 0, got {buffer_m}")
    if min_width_m < 0:
        raise ValueError(f"min_width_m must be >= 0, got {min_width_m}")

    projected = gdf.to_crs(buffer_crs)

    all_rows = []
    total_clusters = 0
    total_dropped = 0
    total_unassigned = 0

    for l2_class, class_gdf in projected.groupby('RB_Type_L2'):
        if show_progress:
            print(f"  {l2_class}: buffering and grouping "
                  f"{len(class_gdf)} reefs", flush=True)

        # Grouping: buffered union per L2 class -> single-part cluster
        # boundaries. Only reefs of the same type can fall into the same
        # cluster.
        union = unary_union(class_gdf.geometry.buffer(buffer_m))
        comps = (
            gpd.GeoDataFrame(geometry=[union], crs=projected.crs)
            .explode(index_parts=False)
            .reset_index(drop=True)
        )
        comps['_comp_id'] = range(len(comps))
        n_clusters = len(comps)
        if show_progress:
            print(f"  {l2_class}: assigning reefs to {n_clusters} clusters",
                  flush=True)

        # Assign each member reef to its cluster via representative point
        # (guaranteed to lie inside the reef, hence inside one cluster),
        # with an intersects fallback for rare floating-point edge cases
        # (same approach as dissolve_to_l2_components).
        members = class_gdf.copy()
        members['_member_idx'] = members.index
        members['geometry'] = members.geometry.representative_point()
        joined = gpd.sjoin(
            members[['_member_idx', 'geometry']],
            comps[['_comp_id', 'geometry']],
            predicate='within',
            how='left',
        )
        unassigned = joined[joined['_comp_id'].isna()]
        if not unassigned.empty:
            un_feats = class_gdf.loc[
                unassigned['_member_idx'].tolist(),
                ['_member_idx', 'geometry'],
            ]
            un_feats['geometry'] = un_feats.geometry.representative_point()
            fallback = gpd.sjoin(
                un_feats, comps[['_comp_id', 'geometry']],
                predicate='intersects', how='left',
            ).drop_duplicates(subset='_member_idx')
            for _, row in fallback.iterrows():
                joined.loc[joined['_member_idx'] == row['_member_idx'],
                           '_comp_id'] = row['_comp_id']
            still = joined[joined['_comp_id'].isna()]
            if not still.empty:
                total_unassigned += len(still)
                print(f"  WARNING: {len(still)} '{l2_class}' reefs could not "
                      f"be assigned to a cluster")

        # Build output rows per cluster
        processed_clusters = 0
        report_every = max(1, n_clusters // 20)
        for comp_id, member_reefs in joined.dropna(subset=['_comp_id']
                                                   ).groupby('_comp_id'):
            processed_clusters += 1
            member_idx = member_reefs['_member_idx'].tolist()
            geom = unary_union(class_gdf.loc[member_idx, 'geometry'])
            # Sliver repair (same as dissolve_to_l2_components) to clean
            # internal seams without changing the extent or the area. In a
            # metre CRS SLIVER_EPS is sub-millimetre, so this is a no-op
            # that only removes redundant vertices.
            geom = geom.buffer(SLIVER_EPS).buffer(-SLIVER_EPS)
            geom = geom.simplify(SLIVER_EPS, preserve_topology=True)
            area_m2 = geom.area
            eff_width = 2.0 * np.sqrt(area_m2 / np.pi)
            if drop_small and eff_width < min_width_m:
                total_dropped += 1
            else:
                all_rows.append({
                    'RB_Type_L2': l2_class,
                    'Area_km2': area_m2 / 1e6,
                    'EffWidth_m': eff_width,
                    'geometry': geom,
                })
            if show_progress and (processed_clusters % report_every == 0 or
                                  processed_clusters == n_clusters):
                print(f"  {l2_class}: {processed_clusters}/{n_clusters} "
                      "clusters processed", flush=True)

        total_clusters += n_clusters

    out = gpd.GeoDataFrame(all_rows, crs=projected.crs).to_crs(gdf.crs)
    if size_classes is not None:
        bins = [lo for _, lo, _ in size_classes] + [np.inf]
        labels = [name for name, _, _ in size_classes]
        out['SizeClass'] = pd.cut(
            out['EffWidth_m'], bins=bins, labels=labels, include_lowest=True
        )

    stats = {
        'n_fused': len(gdf),
        'n_clusters': total_clusters,
        'n_dropped': total_dropped,
        'n_countable': len(out),
        'n_unassigned': total_unassigned,
        'n_by_class': (out['RB_Type_L2'].value_counts().to_dict()
                       if not out.empty else {}),
    }
    return out, stats
