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
3. Clips all reef geometries against the coastline (using geometry.difference)
4. Removes any features that become empty after clipping (i.e., were entirely on land)
5. Saves the resulting clipped features to the output shapefile
"""

import os
import time
import configparser
import geopandas as gpd
from tqdm import tqdm
from shapely.validation import make_valid
import sys

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
    
    # Validate coastline geometries
    print("Validating coastline geometries...")
    invalid_coast_count = 0
    for i, geom in enumerate(coastline_gdf.geometry):
        if not geom.is_valid:
            coastline_gdf.loc[i, 'geometry'] = make_valid(geom)
            invalid_coast_count += 1
    print(f"Fixed {invalid_coast_count} invalid coastline geometries")
    
    # Clip the reef features against the coastline
    print(f"Clipping {len(gdf)} reef features against the coastline...")
    
    # Create a unified coastline geometry
    print("Creating coastline union for clipping (this may take a while)...")
    coast_start_time = time.time()
    coastline_union = coastline_gdf.union_all()
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
    
    # Perform the clipping with progress bar
    print("Clipping features (removing land areas)...")
    clip_start_time = time.time()
    tqdm.pandas(desc="Clipping features")
    gdf['geometry'] = gdf.geometry.progress_apply(clip_geometry)
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

def main():
    # Start timing
    start_time = time.time()
    print("Starting coastline clipping process...")
    
    # Load configuration
    config = configparser.ConfigParser()
    config.read('config.ini')
    download_path = config.get('general', 'in_3p_path')
    
    # Define input and output paths
    input_file = 'data/v0-4/in/Reef-Boundaries_v0-4_edit.shp'
    coastline_file = f"{download_path}/AU_AIMS_Coastline_50k_2024/Split/AU_NESP-MaC-3-17_AIMS_Aus-Coastline-50k_2024_V1-1_split.shp"
    output_dir = 'data/v0-4/out'
    output_file = f"{output_dir}/NW-Aus-Features_v0-4.shp"
    
    # Check if output file is locked
    if check_file_locked(output_file):
        print(f"ERROR: Output file '{output_file}' is currently open or locked by another process. Please close it and try again.")
        sys.exit(1)
        
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Read the input shapefile
    print(f"Reading input shapefile: {input_file}")
    gdf = gpd.read_file(input_file)
    print(f"Input CRS: {gdf.crs}")
    print(f"Loaded {len(gdf)} features")
    
    # Apply coastline clipping
    clipped_gdf = apply_coastline_clipping(gdf, coastline_file)
    
    # Save the result
    print(f"Saving clipped features to: {output_file}")
    clipped_gdf.to_file(output_file)
    
    # Report time taken
    print(f"Process completed in {time.time() - start_time:.2f} seconds")
    print(f"Output saved to {output_file}")

if __name__ == "__main__":
    main()