import geopandas as gpd
import os
from shapely.ops import unary_union
from shapely.geometry import Polygon, MultiPolygon
import configparser

def main():
    """
    Process and correct the Shallow Marine Mask for Northern Australia.
    
    This script applies manual corrections to the semi-automated Shallow Marine Mask
    by adding missed areas and removing false positives based on a correction shapefile.
    
    The Shallow-mask corresponds to a semi-automated mapping of shallow areas, reefs and 
    seagrass areas across northern Australia. It was produced by Lawrey, E. (2025) 
    Semi-automated Shallow Marine Mask for Northern Australia and GBR Derived from 
    Sentinel-2 Imagery (NESP MaC 3.17, AIMS) (Version 1-1) [Data set]. 
    eAtlas. https://doi.org/10.26274/x37r-xk75.
    
    In this process, the Mask-correction is a manual clean up of the semi-automated mask, 
    adding areas that were missed, and clipping out false positive areas.
    
    Input:
    - Original Shallow-mask: Semi-automated mapping of shallow areas
    - Mask-correction: Manual corrections with 'Add' and 'Remove' operations
    
    Output:
    - Corrected Shallow-mask with manual corrections applied
    """
    print("Starting Shallow Marine Mask correction process...")
    
    # Read configuration
    config = configparser.ConfigParser()
    config.read('config.ini')
    download_path = config.get('general', 'in_3p_path')
    
    # Define input and output paths
    shallow_mask_path = os.path.join(download_path, 'AU_AIMS_Shallow-mask', 
                                    'AU_NESP-MaC-3-17_AIMS_Shallow-mask_Low-VLow_V1-1.shp')
    mask_correction_path = os.path.join('data', 'v0-3_qc-1', 'in', 
                                        'Shallow-mask-correct', 'Shallow-mask-correction.shp')
    
    # Create output directory if it doesn't exist
    output_dir = os.path.join('working', '06')
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, 'Shallow-mask_Corrected.shp')
    
    # Load the shapefiles
    print(f"Loading original Shallow-mask from: {shallow_mask_path}")
    shallow_mask = gpd.read_file(shallow_mask_path)
    
    print(f"Loading correction polygons from: {mask_correction_path}")
    mask_correction = gpd.read_file(mask_correction_path)
    
    # Ensure both datasets have the same CRS
    if shallow_mask.crs != mask_correction.crs:
        print(f"Reprojecting correction polygons from {mask_correction.crs} to {shallow_mask.crs}")
        mask_correction = mask_correction.to_crs(shallow_mask.crs)
    
    # Split correction polygons by operation
    add_polygons = mask_correction[mask_correction['Operation'] == 'Add']
    remove_polygons = mask_correction[mask_correction['Operation'] == 'Remove']
    
    print(f"Processing {len(add_polygons)} 'Add' polygons and {len(remove_polygons)} 'Remove' polygons...")
    
    # SIMPLIFIED APPROACH:
    
    # 1. Filter only polygon geometries from the original mask
    print("Extracting valid polygon geometries from original mask...")
    original_geometries = []
    for geom in shallow_mask.geometry:
        if isinstance(geom, (Polygon, MultiPolygon)) and geom.is_valid:
            original_geometries.append(geom)
    
    # 2. Filter only polygon geometries from 'Add' geometries
    add_geometries = []
    for geom in add_polygons.geometry:
        if isinstance(geom, (Polygon, MultiPolygon)) and geom.is_valid:
            add_geometries.append(geom)
    
    # 3. Combine all geometries and dissolve
    print("Combining original mask with 'Add' polygons...")
    combined_geometries = original_geometries + add_geometries
    dissolved_geometry = unary_union(combined_geometries)
    print("Dissolved all features into a single geometry")
    
    # 4. Apply 'Remove' operation if there are any remove polygons
    if len(remove_polygons) > 0:
        print("Applying 'Remove' polygons...")
        # Filter only valid polygons from remove_polygons
        remove_geometries = []
        for geom in remove_polygons.geometry:
            if isinstance(geom, (Polygon, MultiPolygon)) and geom.is_valid:
                remove_geometries.append(geom)
        
        remove_geometry = unary_union(remove_geometries)
        result_geometry = dissolved_geometry.difference(remove_geometry)
        print("Remove operation completed")
    else:
        result_geometry = dissolved_geometry
    
    # 5. Convert to single part polygons and ensure they're all valid Polygons
    print("Converting to single part polygons...")
    single_part_geometries = []
    
    # Function to process geometries based on their type
    def process_geometry(geom):
        if isinstance(geom, Polygon):
            if geom.is_valid and not geom.is_empty:
                single_part_geometries.append(geom)
        elif isinstance(geom, MultiPolygon):
            for poly in geom.geoms:
                if poly.is_valid and not poly.is_empty:
                    single_part_geometries.append(poly)
    
    # Process the result geometry
    if isinstance(result_geometry, (Polygon, MultiPolygon)):
        process_geometry(result_geometry)
    else:
        print(f"WARNING: Result geometry is of type {type(result_geometry).__name__}, not Polygon or MultiPolygon")
        # Try to extract any polygons from it if possible
        try:
            for geom in result_geometry.geoms:
                if isinstance(geom, (Polygon, MultiPolygon)):
                    process_geometry(geom)
        except (AttributeError, TypeError):
            print("Unable to extract polygons from result geometry")
    
    print(f"Extracted {len(single_part_geometries)} valid polygons")
    
    if not single_part_geometries:
        print("ERROR: No valid polygon geometries found in the result")
        return
    
    # 6. Create a new GeoDataFrame with the results
    # Use one row from shallow_mask as a template for attributes
    template_row = shallow_mask.iloc[0]
    rows = []
    
    for geom in single_part_geometries:
        new_row = template_row.copy()
        new_row.geometry = geom
        rows.append(new_row)
    
    # Create the final GeoDataFrame
    result_gdf = gpd.GeoDataFrame(rows, crs=shallow_mask.crs)
    
    print(f"Final corrected dataset contains {len(result_gdf)} features")
    
    # Save the result - explicitly specify the geometry type
    print(f"Saving corrected Shallow-mask to: {output_path}")
    result_gdf.to_file(output_path, driver='ESRI Shapefile')
    
    print("Shallow Marine Mask correction process completed successfully.")

if __name__ == "__main__":
    main()