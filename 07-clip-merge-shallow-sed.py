#!/usr/bin/env python3
"""
07-v0-3-clip-merge-shallow-sed.py
---------------------------------
This script clips the Shallow-mask with all features from NW-Aus-Features to 
create a layer representing shallow masked areas not covered by reef features.
The resulting shallow sediment features are then added to the NW-Aus-Features 
dataset with specific attribute values.

Inputs:
- NW-Aus-Features: working/05/NW-Aus-Features_v0-3-clean-rocks.shp (reef boundaries)
- Shallow-mask: working/06/Shallow-mask_Corrected.shp (shallow features)

Output:
- working/07/NW-Aus-Features-sediment.shp (combined dataset with new shallow sediment features)
"""

import os
import pandas as pd
import geopandas as gpd
from pathlib import Path
from shapely.ops import unary_union
from shapely.geometry import Polygon, MultiPolygon, GeometryCollection

# Define input and output paths
nw_features_path = "working/05/NW-Aus-Features_v0-3-clean-rocks.shp"
shallow_mask_path = "working/06/Shallow-mask_Corrected.shp"
output_dir = "working/07"
output_path = f"{output_dir}/NW-Aus-Features-sediment.shp"

# Create output directory if it doesn't exist
Path(output_dir).mkdir(parents=True, exist_ok=True)

# Define default values for shallow sediment features
default_vals = {
    'EdgeSrc': 'Semi-auto shallow mask',
    'Notes': None,
    'FeatConf': 'Medium',
    'TypeConf': 'Medium',
    'EdgeAcc_m': 250,
    'RB_Type_L3': 'Shallow sediment',
    'DepthCat': None,
    'DepthCatSr': None,
    'Feat_L3': 'Shallow Sediment',
    'GeoAttach': 'Fringing',
    'Relief': 'Low',
    'FlowInflu': 'Unknown',
    'SO_L2': 'Terrigenous',
    'Paleo': 'No'
}

# Helper function to handle different geometry types after difference operation
def process_geometry(geom):
    """Process geometry after difference operation to ensure valid polygon types"""
    if geom is None or geom.is_empty:
        return None
    elif isinstance(geom, (Polygon, MultiPolygon)):
        return geom
    elif isinstance(geom, GeometryCollection):
        # Extract only polygons from the collection
        polygons = [g for g in geom.geoms if isinstance(g, (Polygon, MultiPolygon))]
        if not polygons:
            return None
        elif len(polygons) == 1:
            return polygons[0]
        else:
            return MultiPolygon(polygons)
    else:
        # Try to extract polygons from other geometry types
        try:
            if hasattr(geom, 'geoms'):
                polygons = [g for g in geom.geoms if isinstance(g, (Polygon, MultiPolygon))]
                if not polygons:
                    return None
                elif len(polygons) == 1:
                    return polygons[0]
                else:
                    return MultiPolygon(polygons)
        except:
            pass
        return None

def main():
    print("=== Clipping Shallow-mask with NW-Aus-Features ===")
    
    # Load shapefiles
    print(f"Loading NW-Aus-Features from: {nw_features_path}")
    nw_features = gpd.read_file(nw_features_path)
    print(f"Found {len(nw_features)} features in NW-Aus-Features")
    
    print(f"Loading Shallow-mask from: {shallow_mask_path}")
    shallow_mask = gpd.read_file(shallow_mask_path)
    print(f"Found {len(shallow_mask)} features in Shallow-mask")
    
    # Ensure both datasets have the same CRS
    if shallow_mask.crs != nw_features.crs:
        print(f"Reprojecting Shallow-mask from {shallow_mask.crs} to {nw_features.crs}")
        shallow_mask = shallow_mask.to_crs(nw_features.crs)
    
    # Dissolve all NW-Aus-Features into a single geometry for clipping
    print("Dissolving all NW-Aus-Features for clipping...")
    all_nw_geometries = list(nw_features.geometry)
    dissolved_nw = unary_union(all_nw_geometries)
    print("Dissolved all NW-Aus-Features into a single geometry")
    
    # Clip Shallow-mask with the dissolved NW-Aus-Features
    print("Clipping Shallow-mask with NW-Aus-Features...")
    
    # Process each polygon in the Shallow-mask
    clipped_shallow_features = []
    skipped_count = 0
    total = len(shallow_mask)
    
    for i, shallow_row in shallow_mask.iterrows():
        if i % 100 == 0 or i == total - 1:
            print(f"Processing {i+1}/{total} Shallow-mask polygons")
        
        shallow_geom = shallow_row.geometry
        
        # Skip invalid geometries
        if not shallow_geom.is_valid or shallow_geom.is_empty:
            skipped_count += 1
            continue
        
        # Clip the Shallow-mask polygon with the dissolved NW-Aus-Features
        clipped_geom = shallow_geom.difference(dissolved_nw)
        
        # Process the resulting geometry to ensure it's a valid polygon type
        processed_geom = process_geometry(clipped_geom)
        
        if processed_geom is not None and not processed_geom.is_empty:
            # Split MultiPolygons into individual Polygons
            if isinstance(processed_geom, MultiPolygon):
                for single_poly in processed_geom.geoms:
                    if single_poly.is_valid and not single_poly.is_empty:
                        feature_data = default_vals.copy()
                        feature_data['geometry'] = single_poly
                        clipped_shallow_features.append(feature_data)
            else:
                feature_data = default_vals.copy()
                feature_data['geometry'] = processed_geom
                clipped_shallow_features.append(feature_data)
    
    print(f"Skipped {skipped_count} invalid or empty Shallow-mask polygons")
    print(f"Created {len(clipped_shallow_features)} new shallow sediment features")
    
    # Create a GeoDataFrame from the clipped shallow features
    if not clipped_shallow_features:
        print("No valid shallow sediment features were created after clipping")
        shallow_sediment_gdf = gpd.GeoDataFrame([], crs=nw_features.crs)
    else:
        shallow_sediment_gdf = gpd.GeoDataFrame(clipped_shallow_features, crs=nw_features.crs)
    
    # Make sure all columns from NW-Aus-Features exist in shallow_sediment_gdf
    for col in nw_features.columns:
        if col not in shallow_sediment_gdf.columns and col != 'geometry':
            shallow_sediment_gdf[col] = None
    
    # Combine NW-Aus-Features with the new shallow sediment features
    print("Combining NW-Aus-Features with new shallow sediment features...")
    result_gdf = pd.concat([nw_features, shallow_sediment_gdf], ignore_index=True)
    result_gdf = gpd.GeoDataFrame(result_gdf, crs=nw_features.crs)
    
    print(f"Final dataset contains {len(result_gdf)} features")
    
    # Save the result
    print(f"Saving result to {output_path}")
    result_gdf.to_file(output_path)
    
    print("Processing complete!")

if __name__ == "__main__":
    main()