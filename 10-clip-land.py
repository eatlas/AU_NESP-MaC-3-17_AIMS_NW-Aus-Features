"""
NW-Aus-Features Coastline Clipping Script
-----------------------------------------
This script clips the NW-Aus-Features dataset against the Australian coastline to
remove any portions of features that overlap with land.

Background:
The NW-Aus-Features dataset is a mapping of rocky and coral reefs of northern Australia.
During the manual digitisation process, features were only loosely digitised on the
landward side to improve digitisation speed, with the knowledge that a subsequent
clipping operation would clean these boundaries. This script performs that clipping
operation using a high-resolution coastline dataset.

Process:
1. Loads the reef features from the input shapefile
2. Loads the coastline shapefile
3. Performs a series of geometry checks on the input and coastline data:
   - Checks for empty or null geometries
   - Checks for invalid geometries (e.g., self-intersections)
   - Checks for non-polygon geometries
   - Reports and saves problematic features for manual inspection
4. Clips all reef geometries against the coastline (using geometry.difference)
5. Removes any features that become empty after clipping (i.e., were entirely on land)
6. Saves the resulting clipped features to the output shapefile
"""

import os
import time
import configparser
import geopandas as gpd
from tqdm import tqdm
from shapely.validation import make_valid, explain_validity
from shapely.prepared import prep
from concurrent.futures import ThreadPoolExecutor
import sys

cfg = configparser.ConfigParser()
cfg.read("config.ini")
in_3p_path = cfg.get("general", "in_3p_path")
version = cfg.get("general", "version")

# ---- PATH CONSTANTS ----
OUTPUT_DIR = f'working/{version}/10'
INPUT_FILE = f'data/{version}/in/Reef-Boundaries_{version}_edit.shp'
OUTPUT_FILE = f"{OUTPUT_DIR}/NW-Aus-Features_{version}.shp"
NONPOLY_INPUT_FILE = f"{OUTPUT_DIR}/NW-Aus-Features_{version}_input_nonpolygons.shp"
NONPOLY_CLIPPED_FILE = f"{OUTPUT_DIR}/NW-Aus-Features_{version}_clipped_nonpolygons.shp"
INVALID_GEOM_PATH = f"{OUTPUT_DIR}/NW-Aus-Features_{version}_input_invalid.shp"
# coastline_file is built in main as it depends on config

def apply_coastline_clipping(gdf, coastline_file):
    """
    Applies coastline clipping to remove overlapping land areas from reef features.

    Args:
        gdf: GeoDataFrame containing reef features
        coastline_file: Path to the coastline shapefile

    Returns:
        GeoDataFrame with clipped geometries
    """
    start_time = time.time()

    # Read the coastline data
    print(f"Reading coastline shapefile from: {coastline_file}")
    coastline_gdf = gpd.read_file(coastline_file)
    print(f"Coastline CRS: {coastline_gdf.crs}")
    print(f"Loaded {len(coastline_gdf)} coastline features in {time.time() - start_time:.2f} seconds")

    # Ensure both datasets are in the same CRS (EPSG:4326)
    if gdf.crs and gdf.crs != "EPSG:4326":
        print(f"Converting reef features from {gdf.crs} to EPSG:4326")
        gdf = gdf.to_crs(epsg=4326)

    if coastline_gdf.crs and coastline_gdf.crs != "EPSG:4326":
        print(f"Converting coastline from {coastline_gdf.crs} to EPSG:4326")
        coastline_gdf = coastline_gdf.to_crs(epsg=4326)

    # Fail fast: check for empty geometries in input
    empty_input = gdf[gdf.geometry.is_empty | gdf.geometry.isna()]
    if not empty_input.empty:
        raise ValueError(f"Input GeoDataFrame contains {len(empty_input)} empty or null geometries. Please fix before proceeding.")

    # Fail fast: check for invalid geometries in input
    invalid_input = gdf[~gdf.geometry.is_valid]
    if not invalid_input.empty:
        print(f"Saving {len(invalid_input)} invalid input geometries to {INVALID_GEOM_PATH}")
        os.makedirs(os.path.dirname(INVALID_GEOM_PATH), exist_ok=True)
        invalid_input.to_file(INVALID_GEOM_PATH)
        # Print details about invalid geometries
        print("Details of invalid geometries:")
        for idx, row in invalid_input.iterrows():
            reason = explain_validity(row.geometry)
            print(f"Feature index {idx}: {reason}")
        raise ValueError(f"Input GeoDataFrame contains {len(invalid_input)} invalid geometries. Saved to {INVALID_GEOM_PATH}. Please fix before proceeding.")
    # Fail fast: check for non-polygon geometries in input
    from shapely.geometry import Polygon, MultiPolygon
    nonpoly_input = gdf[~gdf.geometry.apply(lambda g: isinstance(g, (Polygon, MultiPolygon)))]
    if not nonpoly_input.empty:
        raise ValueError(f"Input GeoDataFrame contains {len(nonpoly_input)} non-polygon geometries. Please fix before proceeding.")

    # After CRS conversion, check for invalid geometries in coastline
    invalid_coast = coastline_gdf[~coastline_gdf.geometry.is_valid]
    if not invalid_coast.empty:
        raise ValueError(f"Coastline GeoDataFrame contains {len(invalid_coast)} invalid geometries after CRS conversion. Please fix before proceeding.")

    # Fail fast: check for non-polygon geometries in coastline
    nonpoly_coast = coastline_gdf[~coastline_gdf.geometry.apply(lambda g: isinstance(g, (Polygon, MultiPolygon)))]
    if not nonpoly_coast.empty:
        raise ValueError(f"Coastline GeoDataFrame contains {len(nonpoly_coast)} non-polygon geometries. Please fix before proceeding.")

    # Clip the reef features against the coastline
    print(f"Clipping {len(gdf)} reef features against the coastline...")

    # Create a unified coastline geometry
    print("Creating coastline union for clipping (this may take a while)...")
    coast_start_time = time.time()
    coastline_union = coastline_gdf.union_all()
    # Fail fast: check for empty or invalid union
    if coastline_union.is_empty:
        raise RuntimeError("Coastline union geometry is empty. Aborting.")
    if not coastline_union.is_valid:
        raise RuntimeError("Coastline union geometry is invalid. Aborting.")
    print(f"Coastline union created in {time.time() - coast_start_time:.2f} seconds")

    # Function to clip a geometry against the coastline
    def clip_geometry(geom):
        if geom is None:
            return None
        try:
            # Make sure the geometry is valid before clipping
            if not geom.is_valid:
                geom = make_valid(geom)

            # Perform the difference operation (remove land areas)
            clipped = geom.difference(coastline_union)

            # Validate the resulting geometry
            if not clipped.is_empty and not clipped.is_valid:
                clipped = make_valid(clipped)

            # Return None if the result is empty
            if clipped.is_empty:
                return None
            return clipped
        except Exception as e:
            print(f"Error in clipping: {e}")
            # Try to recover using make_valid rather than returning the original
            try:
                valid_geom = make_valid(geom)
                return valid_geom.difference(coastline_union)
            except Exception:
                return geom

    # Pre-filter: identify features that actually intersect the coastline
    # Uses a prepared geometry for fast predicate testing against the
    # actual coastline shape (not just its bounding box).
    print("Pre-filtering features against coastline...")
    prefilter_start = time.time()
    prepared_coast = prep(coastline_union)
    needs_clip_mask = gdf.geometry.apply(prepared_coast.intersects)
    clip_count = needs_clip_mask.sum()
    skip_count = len(gdf) - clip_count
    print(f"Pre-filter completed in {time.time() - prefilter_start:.2f} seconds: "
          f"{clip_count} features intersect coastline, {skip_count} skipped")

    # Clip intersecting features using a thread pool for parallelism.
    # Shapely 2.x releases the GIL during GEOS operations, so threads
    # achieve true parallelism without serialisation overhead.
    print(f"Clipping {clip_count} features using thread pool...")
    clip_start_time = time.time()

    geoms_to_clip = gdf.loc[needs_clip_mask, 'geometry'].tolist()
    indices_to_clip = gdf.loc[needs_clip_mask].index

    with ThreadPoolExecutor() as executor:
        results = list(tqdm(
            executor.map(clip_geometry, geoms_to_clip),
            total=len(geoms_to_clip),
            desc="Clipping features"
        ))

    gdf.loc[indices_to_clip, 'geometry'] = results
    print(f"Clipping completed in {time.time() - clip_start_time:.2f} seconds")

    # Remove any features that became empty after clipping
    original_count = len(gdf)
    gdf = gdf[~gdf.geometry.isna() & ~gdf.geometry.is_empty]
    removed_count = original_count - len(gdf)
    print(f"Removed {removed_count} features that were completely on land")

    return gdf

def check_file_locked(filepath):
    """
    Checks if a shapefile is locked by attempting to read and write it.
    Returns True if locked, False otherwise.
    """
    if not os.path.exists(filepath):
        return False

    try:
        # Try to read the shapefile
        test_gdf = gpd.read_file(filepath)

        # If read succeeds, try to write it back (the real test for locks)
        test_gdf.to_file(filepath)
        return False
    except (PermissionError, OSError) as e:
        print(f"Lock detection: {str(e)}")
        return True
    except Exception as e:
        # Other errors might indicate file corruption or other issues
        print(f"Warning during lock check: {str(e)}")
        # We don't consider these as locks, but as other potential issues
        return False

def is_polygon(geom):
    """Return True if geometry is Polygon or MultiPolygon."""
    from shapely.geometry import Polygon, MultiPolygon
    return geom is not None and (isinstance(geom, Polygon) or isinstance(geom, MultiPolygon))

def main():
    # Start timing
    start_time = time.time()
    print("Starting coastline clipping process...")

    coastline_file = f"{in_3p_path}/AU_AIMS_Coastline_50k_2024/Split/AU_NESP-MaC-3-17_AIMS_Aus-Coastline-50k_2024_V1-1_split.shp"

    # Check if output file is locked
    if check_file_locked(OUTPUT_FILE):
        print(f"ERROR: Output file '{OUTPUT_FILE}' is currently open or locked by another process. Please close it and try again.")
        sys.exit(1)

    # Create output directory if it doesn't exist
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Read the input shapefile
    print(f"Reading input shapefile: {INPUT_FILE}")
    gdf = gpd.read_file(INPUT_FILE)
    print(f"Input CRS: {gdf.crs}")
    print(f"Loaded {len(gdf)} features")

    # --- Check for non-polygon geometries in input ---
    from shapely.geometry import Polygon, MultiPolygon
    nonpoly_input = gdf[~gdf.geometry.apply(lambda g: is_polygon(g))]
    if not nonpoly_input.empty:
        print(f"WARNING: {len(nonpoly_input)} non-polygon geometries found in input. Saving to {NONPOLY_INPUT_FILE}")
        nonpoly_input.to_file(NONPOLY_INPUT_FILE)
    else:
        print("All input features are polygons or multipolygons.")
    gdf = gdf[gdf.geometry.apply(lambda g: is_polygon(g))]

    # Apply coastline clipping
    clipped_gdf = apply_coastline_clipping(gdf, coastline_file)

    # --- After clipping: separate polygons and non-polygons ---
    is_poly_mask = clipped_gdf.geometry.apply(lambda g: is_polygon(g))
    polygons_gdf = clipped_gdf[is_poly_mask]
    nonpoly_clipped = clipped_gdf[~is_poly_mask]

    print(f"Saving {len(polygons_gdf)} polygon features to: {OUTPUT_FILE}")
    polygons_gdf.to_file(OUTPUT_FILE)

    if not nonpoly_clipped.empty:
        print(f"WARNING: {len(nonpoly_clipped)} non-polygon geometries after clipping. Saving to {NONPOLY_CLIPPED_FILE}")
        nonpoly_clipped.to_file(NONPOLY_CLIPPED_FILE)
    else:
        print("All clipped features are polygons or multipolygons.")

    # Report time taken
    print(f"Process completed in {time.time() - start_time:.2f} seconds")
    print(f"Output saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()