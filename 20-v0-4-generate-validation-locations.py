"""
# Validation Location Generator for Reef Features Dataset

## Purpose
This script generates validation locations for reef features in Northwest Australia.
The purpose is to create standardized validation points that can be used to assess
the quality and consistency of reef feature mapping across different versions of the
dataset. By creating these reference points, we can automatically validate updates
to the mapped features without requiring manual re-evaluation.

## Multi-Validator Support
The script creates separate output files for each validator person (identified by their
initials, e.g., 'EL', 'RB'). Each validator receives an identical set of initial
validation datasets, which they can then modify independently. This approach:

1. Allows comparison between different validators' assessments
2. Prevents mix-ups between different validators' work
3. Organizes files in validator-specific directories

For each validator, the files are saved in this structure:
working/20/{validator_initials}/NW-Aus-Features-v0-4_Feature-centroid-{batch}_{validator_initials}.shp

## Methodology
The script implements a stratified random sampling approach:

1. **Spatial Stratification**: 
   - The study area is divided into 12 regions using the validation regions shapefile
   - Features are assigned to regions based on their centroids
   - For each region, a fixed number of features (10 by default) are randomly selected
   - This ensures validation points are distributed throughout the study area

2. **Three Validation Datasets**:
   - **Feature-centroid**: Points at the center of each feature with validation attributes
     (FeatExists, TypeConf, RB_Type_L3, FeatConf, Attachment)
     This allows the person developing the validation dataset to record the attributes of 
     the feature being validated. These attributes can then be compared with the mapped features
     and other people that have also validated the same feature.
   - **Polygon-extent**: Either a simplified and randomly fuzzed polygon representing feature boundaries,
     or a bounding box of the fuzzed polygon (depending on a global setting).
     The bounding box option provides the validator with only the approximate size and location of the feature,
     minimizing bias in interpreting the boundary.
   - **Boundary-error**: Random points along feature boundaries (not on land)
     - Small features (<1km perimeter): 1 boundary point
     - Larger features: 3 boundary points
     The intention is that the person developing the validation dataset will adjust these points
     to the most accurate estimate of the true edge of the boundary being mapped.

3. **Processing Steps**:
   - Features are simplified using a tolerance of 50m
   - Random fuzzing (±50m) is applied to vertices for more realistic validation
   - For polygon-extent, a global constant determines whether to output the fuzzed polygon or its bounding box
   - For boundary points, we check against a coastline dataset to ensure they're not on land
   - If a point is on land, we retry up to a maximum number of attempts

4. **Batch Processing**:
   - Features are processed in batches, with each batch creating its own set of files
   - Each batch uses different features to ensure broader coverage
   - A fixed random seed ensures reproducibility between runs

## Outputs
The script produces three shapefiles per batch:
   - NW-Aus-Features-v0-4_Feature-centroid-XX.shp
   - NW-Aus-Features-v0-4_Polygon-extent-XX.shp
   - NW-Aus-Features-v0-4_Boundary-error-XX.shp

Where XX is the batch number (01, 02, etc.)

These validation datasets can be used to automatically assess:
   - Whether features exist in the expected locations
   - Whether feature type classification is consistent
   - How accurately boundaries are mapped relative to validated boundary points
"""

import geopandas as gpd
import numpy as np
import random
import os
import configparser
from shapely.geometry import Point, LineString, Polygon, MultiPolygon
import pandas as pd
from tqdm import tqdm

# Load config file to get base path
config = configparser.ConfigParser()
config.read('config.ini')
BASE_PATH = config.get('general', 'in_3p_path')

# Constants
# This collection was made to act as an example to explain how the validation
# works. These results are reviewed by all validations and thus are not
# intended to be used for validation of the dataset.
RANDOM_SEED = 314
NUM_BATCHES = 1
FEATURES_PER_REGION = 2
VALIDATORS = ['Examples']  

# This collection is used for the production validation dataset.
# RANDOM_SEED = 42  
# NUM_BATCHES = 10
# FEATURES_PER_REGION = 10

# Initials of the people who will validate the dataset
# This will create a copy of the validation data per person
# VALIDATORS = ['EL', 'RB']  


SIMPLIFY_TOLERANCE = 50  # meters
FUZZ_DISTANCE = 100  # meters for vertex fuzzing
SMALL_BOUNDARY_POINTS_PER_FEATURE = 1 
LARGE_BOUNDARY_POINTS_PER_FEATURE = 1 
SMALL_SIZE_THRESHOLD_M = 2000  # Threshold for small features in meters
MAX_ATTEMPTS_PER_POINT = 10  # Maximum attempts to find a point not on land

# Global constant to control whether to use bounding box for polygon-extent
POLYGON_EXTENT_USE_BOUNDING_BOX = True  # Set to True to use bounding box, False for fuzzed polygon

# File paths
VALIDATION_REGIONS_FILE = "data/v0-4/in/NW-Aus-Features-validation-regions.shp"
FEATURES_FILE = "data/v0-4/in/Reef-Boundaries_v0-4_edit.shp"
COASTLINE_FILE = f"{BASE_PATH}/AU_AIMS_Coastline_50k_2024/Split/AU_NESP-MaC-3-17_AIMS_Aus-Coastline-50k_2024_V1-1_split.shp"
OUTPUT_DIR = "working/20"

def load_data():
    """Load the validation regions, reef features, and coastline datasets"""
    print("Loading validation regions...")
    regions = gpd.read_file(VALIDATION_REGIONS_FILE)
    print(f"Loaded {len(regions)} validation regions with CRS: {regions.crs}")
    
    print("Loading reef features...")
    features = gpd.read_file(FEATURES_FILE)
    print(f"Loaded {len(features)} reef features with CRS: {features.crs}")
    
    print("Loading coastline...")
    coastline = gpd.read_file(COASTLINE_FILE)
    print(f"Loaded {len(coastline)} coastline features with CRS: {coastline.crs}")
    
    # Print bounding boxes for debugging
    print(f"Features bounding box: {features.total_bounds}")
    print(f"Regions bounding box: {regions.total_bounds}")
    
    return regions, features, coastline

def assign_features_to_regions(features, regions):
    """Assign features to regions based on their centroids"""
    print("Assigning features to regions...")
    # Calculate centroids for spatial join
    features_centroids = features.copy()
    features_centroids['geometry'] = features_centroids.geometry.centroid
    
    print(f"Feature centroids CRS: {features_centroids.crs}")
    print(f"Regions CRS: {regions.crs}")
    
    # Check if CRS are compatible or need transformation
    if features_centroids.crs != regions.crs:
        print(f"WARNING: CRS mismatch! Converting features from {features_centroids.crs} to {regions.crs}")
        features_centroids = features_centroids.to_crs(regions.crs)
    
    # Spatial join to assign region
    features_with_region = gpd.sjoin(features_centroids, regions, how="left", predicate="within")
    
    # Count how many features were assigned to regions
    unassigned = features_with_region[features_with_region['RegionID'].isna()]
    assigned = features_with_region[~features_with_region['RegionID'].isna()]
    print(f"Features assigned to regions: {len(assigned)} of {len(features_with_region)}")
    print(f"Features NOT assigned to any region: {len(unassigned)}")
    
    if len(assigned) == 0:
        print("ERROR: No features were assigned to any region!")
        print("Checking if features intersect with regions at all...")
        # Try a different spatial predicate
        intersects_join = gpd.sjoin(features_centroids, regions, how="left", predicate="intersects")
        intersects_count = len(intersects_join[~intersects_join['RegionID'].isna()])
        print(f"Features that intersect with regions: {intersects_count}")
        
        # Sample a few features and check their coordinates
        print("Sample feature centroid coordinates:")
        sample_size = min(5, len(features_centroids))
        for i, (idx, row) in enumerate(features_centroids.iloc[:sample_size].iterrows()):
            print(f"  Feature {i}: {row.geometry.x}, {row.geometry.y}")
    
    # Group features by region
    features_by_region = {}
    for region_id in regions['RegionID'].unique():
        region_features = features_with_region[features_with_region['RegionID'] == region_id]
        if not region_features.empty:
            # Get the original geometries for these features
            region_indices = region_features.index
            region_features = features.loc[region_indices].copy()
            features_by_region[region_id] = region_features
            print(f"Region {region_id}: {len(region_features)} features")
        else:
            # Create a proper empty GeoDataFrame with a geometry column
            features_by_region[region_id] = gpd.GeoDataFrame({'geometry': []}, crs=features.crs)
            print(f"Region {region_id}: No features")
    
    return features_by_region

def convert_to_crs_units(distance_m, crs):
    """Convert distance from meters to units of the CRS"""
    if crs.is_geographic:  # If the CRS is in degrees (geographic)
        # Rough approximation - 1 degree is about 111 km at the equator
        return distance_m / 111000
    else:  # Projected CRS - units are likely meters already
        return distance_m

def simplify_and_fuzz_polygon(polygon, crs):
    """Simplify a polygon and apply random fuzzing to its vertices, then return either the fuzzed polygon or its bounding box."""
    # Convert distances to appropriate units
    tolerance_units = convert_to_crs_units(SIMPLIFY_TOLERANCE, crs)
    fuzz_distance_units = convert_to_crs_units(FUZZ_DISTANCE, crs)
    
    # Simplify the polygon
    simplified = polygon.simplify(tolerance_units)
    
    # Apply fuzzing to vertices
    def fuzz_coords(coords):
        return [(x + random.uniform(-fuzz_distance_units, fuzz_distance_units),
                 y + random.uniform(-fuzz_distance_units, fuzz_distance_units)) for x, y in coords]
    
    if simplified.geom_type == 'Polygon':
        exterior_coords = list(simplified.exterior.coords)
        fuzzed_coords = fuzz_coords(exterior_coords)
        fuzzed_polygon = Polygon(fuzzed_coords)
    elif simplified.geom_type == 'MultiPolygon':
        fuzzed_parts = []
        for part in simplified.geoms:
            exterior_coords = list(part.exterior.coords)
            fuzzed_coords = fuzz_coords(exterior_coords)
            fuzzed_parts.append(Polygon(fuzzed_coords))
        fuzzed_polygon = MultiPolygon(fuzzed_parts)
    else:
        fuzzed_polygon = simplified  # fallback
    
    if POLYGON_EXTENT_USE_BOUNDING_BOX:
        # Return the bounding box as a Polygon
        minx, miny, maxx, maxy = fuzzed_polygon.bounds
        return Polygon([
            (minx, miny),
            (minx, maxy),
            (maxx, maxy),
            (maxx, miny),
            (minx, miny)
        ])
    else:
        return fuzzed_polygon

def generate_boundary_points(polygon, crs, coastline):
    """
    Generate random points along the boundary of a polygon,
    excluding points that overlap with land areas.
    Number of points depends on feature size:
    - Small features (perimeter < 1km): 1 point
    - Larger features: 3 points
    """
    # Get the boundary of the polygon
    boundary = polygon.boundary
    
    # Calculate perimeter length in meters (approx)
    perimeter = 0
    if boundary.geom_type == 'LineString':
        perimeter = boundary.length
    elif boundary.geom_type == 'MultiLineString':
        perimeter = sum(line.length for line in boundary.geoms)
    else:
        print(f"Warning: Unexpected geometry type: {boundary.geom_type}")
        return []
    
    # If using geographic coordinates, convert to approximate meters
    if crs.is_geographic:
        # Rough conversion: 1 degree ~ 111km at equator
        perimeter = perimeter * 111000
    
    # Determine number of points based on size
    num_points = SMALL_BOUNDARY_POINTS_PER_FEATURE \
        if perimeter < SMALL_SIZE_THRESHOLD_M else LARGE_BOUNDARY_POINTS_PER_FEATURE
    
    # Handle different geometry types
    if boundary.geom_type == 'LineString':
        lines = [boundary]
    elif boundary.geom_type == 'MultiLineString':
        lines = list(boundary.geoms)
    else:
        print(f"Warning: Unexpected geometry type: {boundary.geom_type}")
        return []
    
    # Calculate the total length of all line segments
    total_length = sum(line.length for line in lines)
    
    # Generate points and check against coastline
    valid_points = []
    attempts = 0
    max_attempts = num_points * MAX_ATTEMPTS_PER_POINT
    
    while len(valid_points) < num_points and attempts < max_attempts:
        # Choose a random position along the total length
        pos = random.uniform(0, total_length)
        
        # Find which line segment this position falls on
        current_length = 0
        point = None
        
        for line in lines:
            if pos <= current_length + line.length:
                # This is the line that contains our point
                position_on_line = pos - current_length
                point = line.interpolate(position_on_line)
                break
            current_length += line.length
        
        if point is not None:
            # Check if the point overlaps with land
            if not coastline.contains(point).any():
                valid_points.append(point)
        
        attempts += 1
    
    if len(valid_points) < num_points:
        print(f"Warning: Could only generate {len(valid_points)} valid boundary points " 
              f"out of {num_points} requested after {attempts} attempts.")
    
    return valid_points

def ensure_centroid_inside(polygon):
    """Ensure the centroid is inside the polygon, or find a point that is"""
    centroid = polygon.centroid
    if polygon.contains(centroid):
        return centroid
    
    # If centroid is not inside, use a point on surface
    return polygon.representative_point()

def create_batch_datasets(features_by_region, batch_num, used_features_indices, coastline):
    """Create the three validation datasets for a batch"""
    print(f"Creating validation datasets for batch {batch_num}...")
    
    # Initialize empty lists for each output
    feature_centroids = []
    polygon_extents = []
    boundary_errors = []
    
    valid_id = 1  # Start ID at 1
    
    # For each region, select features
    for region_id, features in features_by_region.items():
        # Skip if there are no features in this region
        if len(features) == 0:
            print(f"Warning: No features found in region {region_id}")
            continue
        
        # Get features that haven't been used yet
        if region_id not in used_features_indices:
            used_features_indices[region_id] = set()
            
        available_indices = [idx for idx in features.index if idx not in used_features_indices[region_id]]
        
        # Select random features (or all if fewer than requested)
        num_to_select = min(FEATURES_PER_REGION, len(available_indices))
        if num_to_select == 0:
            print(f"Warning: No features left in region {region_id} for batch {batch_num}")
            continue
            
        selected_indices = np.random.choice(available_indices, size=num_to_select, replace=False)
        selected_features = features.loc[selected_indices]
        
        # Mark these features as used
        used_features_indices[region_id].update(selected_indices)
        
        for _, feature in selected_features.iterrows():
            # 1. Feature-centroid
            inside_point = ensure_centroid_inside(feature.geometry)
            centroid_data = {
                'ValidID': valid_id,
                'FeatExists': None,    # NULL default so we can track which features have been processed.
                'FeatConf': None,      # NULL default
                'RB_Type_L3': None,    # NULL default
                'TypeConf': None,      # NULL default
                'Attachment': None,    # NULL default
                'geometry': inside_point
            }
            feature_centroids.append(centroid_data)
            
            # 2. Polygon-extent
            simplified_fuzzed = simplify_and_fuzz_polygon(feature.geometry, features.crs)
            extent_data = {
                'ValidID': valid_id,
                'geometry': simplified_fuzzed
            }
            polygon_extents.append(extent_data)
            
            # 3. Boundary-error - use the simplified and fuzzed polygon for boundary points
            boundary_points = generate_boundary_points(simplified_fuzzed, features.crs, coastline)
            for point in boundary_points:
                boundary_data = {
                    'ValidID': valid_id,
                    'geometry': point
                }
                boundary_errors.append(boundary_data)
            
            valid_id += 1
    
    # Convert to GeoDataFrames
    feature_centroids_gdf = gpd.GeoDataFrame(feature_centroids, crs=features.crs)
    # Reorder columns for Feature-centroid output
    feature_centroids_gdf = feature_centroids_gdf[['ValidID', 'FeatExists', 'FeatConf', 'RB_Type_L3', 'TypeConf', 'Attachment', 'geometry']]
    polygon_extents_gdf = gpd.GeoDataFrame(polygon_extents, crs=features.crs)
    boundary_errors_gdf = gpd.GeoDataFrame(boundary_errors, crs=features.crs)
    
    return feature_centroids_gdf, polygon_extents_gdf, boundary_errors_gdf

def save_validation_datasets(centroids, extents, boundary_points, batch_num):
    """
    Save the validation datasets to shapefiles for each validator.
    Creates separate files for each validator with their initials in the filename
    and organized in validator-specific directories.
    """
    # Create batch string (e.g., "01", "02", etc.)
    batch_str = str(batch_num).zfill(2)
    
    # Loop through each validator
    for validator in VALIDATORS:
        # Create validator-specific output directory
        validator_dir = os.path.join(OUTPUT_DIR, validator)
        os.makedirs(validator_dir, exist_ok=True)
        
        # Define validator-specific filenames
        centroids_file = os.path.join(validator_dir, f"NW-Aus-Features-v0-4_Feature-centroid-{batch_str}_{validator}.shp")
        extents_file = os.path.join(validator_dir, f"NW-Aus-Features-v0-4_Polygon-extent-{batch_str}_{validator}.shp")
        boundary_file = os.path.join(validator_dir, f"NW-Aus-Features-v0-4_Boundary-error-{batch_str}_{validator}.shp")
        
        print(f"Saving Feature-centroid for validator {validator} to {centroids_file}")
        centroids.to_file(centroids_file)
        
        print(f"Saving Polygon-extent for validator {validator} to {extents_file}")
        extents.to_file(extents_file)
        
        print(f"Saving Boundary-error for validator {validator} to {boundary_file}")
        boundary_points.to_file(boundary_file)

def main():
    """Main function to generate validation locations"""
    print("Starting validation location generation...")
    
    # Set random seeds for reproducibility
    random.seed(RANDOM_SEED)
    np.random.seed(RANDOM_SEED)
    print(f"Using random seed: {RANDOM_SEED}")
    
    # Load data
    regions, features, coastline = load_data()
    
    # Assign features to regions
    features_by_region = assign_features_to_regions(features, regions)
    
    # Keep track of which features have been used
    used_features_indices = {}
    
    # Generate batches of validation data
    for batch in range(1, NUM_BATCHES + 1):
        print(f"\nProcessing batch {batch} of {NUM_BATCHES}")
        
        # Create validation datasets
        centroids, extents, boundary_points = create_batch_datasets(
            features_by_region, batch, used_features_indices, coastline
        )
        
        # Save to shapefiles
        save_validation_datasets(centroids, extents, boundary_points, batch)
    
    print("\nValidation location generation complete!")

if __name__ == "__main__":
    main()