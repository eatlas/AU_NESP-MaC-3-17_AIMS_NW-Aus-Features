"""
Reef Feature Clipping Script

This script processes a shapefile containing reef feature polygons, identifying
Rocky Reef features and using them to clip any underlying polygons. The purpose
is to remove overlap between Rocky Reef polygons and other feature types (such as
Coral Reef Shallow), ensuring that the boundaries are clean and non-overlapping.

The script reads the input shapefile, identifies Rocky Reef features based on the
Feat_L3 attribute, removes areas where other features overlap with Rocky Reefs,
and saves the result to a new shapefile.
"""

import os
import pandas as pd
import geopandas as gpd
from pathlib import Path
from shapely.geometry import Polygon, MultiPolygon, GeometryCollection

# Define input and output paths
input_file = "working/04/NW-Aus-Features_v0-3-rocks.shp"
output_file = "working/05/NW-Aus-Features_v0-3-clean-rocks.shp"

# Create output directory if it doesn't exist
output_dir = os.path.dirname(output_file)
Path(output_dir).mkdir(parents=True, exist_ok=True)

print(f"Reading input shapefile: {input_file}")
# Read the shapefile into a GeoDataFrame
gdf = gpd.read_file(input_file)

# Extract Rocky Reef polygons
print("Extracting Rocky Reef polygons")
rocky_reefs = gdf[gdf['Feat_L3'] == 'Rocky Reef'].copy()
non_rocky_reefs = gdf[gdf['Feat_L3'] != 'Rocky Reef'].copy()

print(f"Found {len(rocky_reefs)} Rocky Reef polygons")
print(f"Found {len(non_rocky_reefs)} non-Rocky Reef polygons")

# Helper function to handle different geometry types after difference operation
def process_geometry(geom):
    """Process geometry after difference operation to ensure valid polygon types"""
    if geom.is_empty:
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

# Process non-rocky reef polygons
print("Processing non-Rocky Reef polygons to remove areas that overlap with Rocky Reef polygons")
clipped_non_rocky_reefs = []
skipped_count = 0
total = len(non_rocky_reefs)
intersect_count = 0

for i, non_rocky_row in non_rocky_reefs.iterrows():
    if i % 100 == 0 or i == total - 1:
        print(f"Processing {i+1}/{total} non-Rocky Reef polygons")
    
    non_rocky_geom = non_rocky_row.geometry
    
    # Check if this polygon intersects with any rocky reef
    intersecting_rocky_reefs = rocky_reefs[rocky_reefs.intersects(non_rocky_geom)]
    
    if len(intersecting_rocky_reefs) > 0:
        intersect_count += 1
        # This polygon intersects with at least one rocky reef
        # Clip it using the difference method
        for _, rocky_row in intersecting_rocky_reefs.iterrows():
            rocky_geom = rocky_row.geometry
            if non_rocky_geom.intersects(rocky_geom):
                # Remove the overlapping part
                non_rocky_geom = non_rocky_geom.difference(rocky_geom)
                non_rocky_geom = process_geometry(non_rocky_geom)
                if non_rocky_geom is None:
                    break
        
        # If there's still geometry left after clipping
        if non_rocky_geom is not None and not non_rocky_geom.is_empty:
            non_rocky_row = non_rocky_row.copy()
            non_rocky_row.geometry = non_rocky_geom
            clipped_non_rocky_reefs.append(non_rocky_row)
        else:
            skipped_count += 1
    else:
        # No intersection, keep as is
        clipped_non_rocky_reefs.append(non_rocky_row)

print(f"Found {intersect_count} non-Rocky Reef polygons that intersect with Rocky Reef polygons")
print(f"Skipped {skipped_count} polygons that were completely removed by clipping")

# Convert the list of clipped non-rocky reefs back to a GeoDataFrame
print("Converting clipped results back to a GeoDataFrame")
clipped_non_rocky_gdf = gpd.GeoDataFrame(clipped_non_rocky_reefs, crs=gdf.crs)

# Combine rocky reefs with clipped non-rocky reefs
print("Combining Rocky Reef polygons with clipped non-Rocky Reef polygons")
result_gdf = pd.concat([rocky_reefs, clipped_non_rocky_gdf])
result_gdf = gpd.GeoDataFrame(result_gdf, crs=gdf.crs)

print(f"Final result contains {len(result_gdf)} features")

# Save the result
print(f"Saving result to {output_file}")
result_gdf.to_file(output_file)

print("Processing complete!")