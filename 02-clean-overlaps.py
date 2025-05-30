"""
Reef Boundaries Overlap Cleaning Script
======================================

Purpose:
This script processes a shapefile containing coral reef feature boundaries to remove
overlaps between different reef types according to specific hierarchy rules.

Processing:
1. High Intertidal Coral Reef areas are preserved as-is
2. High Intertidal Coral Reef areas are cut out from Platform Coral Reef features
3. High Intertidal Coral Reef areas are cut out from Fringing Coral Reef features
4. The script identifies any remaining overlaps between features after processing
5. A point shapefile is created to mark the centroids of any remaining overlaps

Input:
- Shapefile containing reef boundaries with RB_Type_L3 attribute that categorizes
  features as "High Intertidal Coral Reef", "Platform Coral Reef", "Fringing Coral Reef", etc.

Outputs:
- Cleaned shapefile with overlaps removed according to the processing rules
- Point shapefile marking locations of any remaining overlaps for review in QGIS

The script preserves all original attributes of the features while modifying 
their geometries to eliminate specified overlaps.
"""

import geopandas as gpd
import pandas as pd
import os
import sys
from datetime import datetime
from shapely.geometry import MultiPolygon, Point

def main():
    print(f"=== Reef Boundaries Overlap Cleaning Script ===")
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Input and output paths
    input_shapefile = "data/v0-3_qc-1/in/Reef Boundaries Review.shp"
    output_dir = "working/02"
    output_shapefile = os.path.join(output_dir, "Reef_Boundaries_Clean.shp")
    overlap_points_shapefile = os.path.join(output_dir, "Overlap_Points.shp")
    
    if not os.path.exists(input_shapefile):
        print(f"Error: Input shapefile not found: {input_shapefile}")
        sys.exit(1)
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Load the shapefile
    print("Loading shapefile...")
    try:
        gdf = gpd.read_file(input_shapefile)
        print(f"Loaded {len(gdf)} features")
    except Exception as e:
        print(f"Error loading shapefile: {str(e)}")
        sys.exit(1)
    
    # Check if RB_Type_L3 is in the columns
    if 'RB_Type_L3' not in gdf.columns:
        print("Error: RB_Type_L3 attribute not found in the shapefile.")
        sys.exit(1)
    
    # Print summary of feature types
    print("\nFeature types summary:")
    type_counts = gdf['RB_Type_L3'].value_counts()
    for type_name, count in type_counts.items():
        print(f"  {type_name}: {count}")
    
    # Separate features by type
    high_intertidal = gdf[gdf['RB_Type_L3'] == 'High Intertidal Coral Reef']
    platform_coral = gdf[gdf['RB_Type_L3'] == 'Platform Coral Reef']
    fringing_coral = gdf[gdf['RB_Type_L3'] == 'Fringing Coral Reef']
    other_features = gdf[~gdf['RB_Type_L3'].isin(['High Intertidal Coral Reef', 'Platform Coral Reef', 'Fringing Coral Reef'])]
    
    print(f"\nHigh Intertidal Coral Reef features: {len(high_intertidal)}")
    print(f"Platform Coral Reef features: {len(platform_coral)}")
    print(f"Fringing Coral Reef features: {len(fringing_coral)}")
    print(f"Other features: {len(other_features)}")
    
    # Function to cut out overlaps
    def cut_out_overlaps(target_gdf, overlay_gdf):
        if len(target_gdf) == 0 or len(overlay_gdf) == 0:
            return target_gdf, 0
            
        modified_features = []
        overlap_count = 0
        
        for idx, target_feature in target_gdf.iterrows():
            modified_geom = target_feature.geometry
            has_overlap = False
            
            for _, overlay_feature in overlay_gdf.iterrows():
                if modified_geom.intersects(overlay_feature.geometry):
                    # Only count as overlap if there's a significant intersection
                    intersection = modified_geom.intersection(overlay_feature.geometry)
                    if intersection.area > 0.0005:  # Threshold to ignore tiny overlaps
                        has_overlap = True
                        overlap_count += 1
                        # Cut out the overlay feature from the target feature
                        modified_geom = modified_geom.difference(overlay_feature.geometry)
            
            # Skip empty or invalid geometries
            if modified_geom is None or modified_geom.is_empty:
                print(f"  Warning: Feature {idx} was completely removed by overlay")
                continue
                
            # Handle potential MultiPolygon results
            if isinstance(modified_geom, MultiPolygon):
                if len(modified_geom.geoms) > 1:
                    print(f"  Feature {idx} became a MultiPolygon with {len(modified_geom.geoms)} parts")
                
            # Copy all attributes to new feature
            new_feature = target_feature.copy()
            new_feature.geometry = modified_geom
            modified_features.append(new_feature)
        
        if not modified_features:
            return gpd.GeoDataFrame(geometry=[], crs=target_gdf.crs), overlap_count
            
        return gpd.GeoDataFrame(modified_features, crs=target_gdf.crs), overlap_count
    
    # Process Platform Coral Reef features
    print("\nCutting out High Intertidal areas from Platform Coral Reefs...")
    modified_platform, platform_overlaps = cut_out_overlaps(platform_coral, high_intertidal)
    print(f"Found and processed {platform_overlaps} overlaps in Platform Coral Reefs")
    
    # Process Fringing Coral Reef features
    print("\nCutting out High Intertidal areas from Fringing Coral Reefs...")
    modified_fringing, fringing_overlaps = cut_out_overlaps(fringing_coral, high_intertidal)
    print(f"Found and processed {fringing_overlaps} overlaps in Fringing Coral Reefs")
    
    # Combine all features back together
    print("\nCombining all features...")
    parts = [modified_platform, modified_fringing, high_intertidal, other_features]
    parts = [part for part in parts if len(part) > 0]  # Filter out empty dataframes
    
    if not parts:
        print("Error: No features left after processing")
        sys.exit(1)
        
    result_gdf = pd.concat(parts, ignore_index=True)
    result_gdf = gpd.GeoDataFrame(result_gdf, crs=gdf.crs)
    
    print(f"Combined dataset has {len(result_gdf)} features")
    
    # Function to check for remaining overlaps
    def identify_overlaps(gdf):
        overlaps = []
        n_features = len(gdf)
        
        print(f"Checking for overlaps among {n_features} features...")
        
        # Use spatial indexing for performance
        try:
            sindex = gdf.sindex
            use_sindex = True
        except Exception:
            use_sindex = False
            print("  Warning: Could not create spatial index, overlap check may be slower")
        
        for i in range(n_features):
            if i % 100 == 0 and i > 0:
                print(f"  Processed {i}/{n_features} features...")
            
            feature_i = gdf.iloc[i]
            geom_i = feature_i.geometry
            type_i = feature_i['RB_Type_L3']
            
            # Skip invalid geometries
            if geom_i is None or geom_i.is_empty:
                continue
                
            # Use spatial index if available
            if use_sindex:
                possible_matches_idx = list(sindex.intersection(geom_i.bounds))
                possible_matches = gdf.iloc[possible_matches_idx]
            else:
                possible_matches = gdf
            
            for j, feature_j in possible_matches.iterrows():
                # Skip self-comparison and already checked pairs
                if i >= j:
                    continue
                    
                geom_j = feature_j.geometry
                type_j = feature_j['RB_Type_L3']
                
                # Skip invalid geometries
                if geom_j is None or geom_j.is_empty:
                    continue
                
                if geom_i.intersects(geom_j) and not geom_i.touches(geom_j):
                    try:
                        intersection = geom_i.intersection(geom_j)
                        if intersection.area > 0.0001:  # Threshold to ignore tiny overlaps
                            # Store only essential information
                            overlaps.append({
                                'feature_i_id': i,
                                'feature_j_id': j,
                                'type_i': type_i,
                                'type_j': type_j,
                                'intersection': intersection
                            })
                    except Exception as e:
                        print(f"  Warning: Error calculating overlap between features {i} and {j}: {str(e)}")
        
        return overlaps
    
    # Check for remaining overlaps
    print("\nIdentifying any remaining overlaps...")
    remaining_overlaps = identify_overlaps(result_gdf)
    
    # Report on remaining overlaps and create point shapefile
    if remaining_overlaps:
        print(f"\nFound {len(remaining_overlaps)} remaining overlaps:")
        
        # Count overlaps by type combination
        overlap_counts = {}
        
        # Create point geometries for overlaps
        point_records = []
        
        for i, overlap in enumerate(remaining_overlaps):
            type_pair_sorted = tuple(sorted([overlap['type_i'], overlap['type_j']]))
            
            # Count by type combination
            if type_pair_sorted not in overlap_counts:
                overlap_counts[type_pair_sorted] = 0
            overlap_counts[type_pair_sorted] += 1
            
            # Create a point at the centroid of the overlap area
            try:
                centroid = overlap['intersection'].centroid
                
                # Create a record for the point shapefile
                point_records.append({
                    'geometry': centroid,
                    'ID': i,
                    'Feature_1': int(overlap['feature_i_id']),
                    'Type_1': overlap['type_i'],
                    'Feature_2': int(overlap['feature_j_id']),
                    'Type_2': overlap['type_j']
                })
            except Exception as e:
                print(f"  Warning: Could not create centroid for overlap {i}: {str(e)}")
        
        # Print summary by type combination
        print("\nOverlap counts by feature type combination:")
        for (type_i, type_j), count in overlap_counts.items():
            print(f"  {type_i} and {type_j}: {count} overlaps")
        
        # Create and save point shapefile for overlaps
        if point_records:
            try:
                points_gdf = gpd.GeoDataFrame(point_records, crs=result_gdf.crs)
                points_gdf.to_file(overlap_points_shapefile)
                print(f"\nSaved {len(points_gdf)} overlap point locations to {overlap_points_shapefile}")
            except Exception as e:
                print(f"Error saving overlap points shapefile: {str(e)}")
    else:
        print("No remaining overlaps found!")
    
    # Save the result to a new shapefile
    print(f"\nSaving cleaned features to {output_shapefile}...")
    try:
        result_gdf.to_file(output_shapefile)
        print(f"Saved {len(result_gdf)} features successfully")
    except Exception as e:
        print(f"Error saving shapefile: {str(e)}")
        sys.exit(1)
    
    print(f"\nEnd time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("Processing complete!")

if __name__ == "__main__":
    main()